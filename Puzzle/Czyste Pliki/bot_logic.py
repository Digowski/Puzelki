"""
Block Solver - Bot Logic Module
Główna logika bota - maszyna stanów i pętla główna.
"""

import time
import threading
from enum import Enum

from config import BLOCK_TYPES, DELAYS, MAX_CHEST_RETRIES
from calibration import Calibrator
from detection import BlockDetector, BoardScanner
from mouse_control import MouseController, ActionSequencer
from board_state import BoardState


class BotState(Enum):
    """Stany bota."""
    IDLE = "Gotowy"
    RUNNING = "Działa..."
    PAUSED = "Pauza"
    FETCHING = "Pobieram klocek..."
    DETECTING = "Rozpoznaję..."
    PLACING = "Kładę klocek..."
    DISCARDING = "Odrzucam..."
    COMPLETING = "Kończę planszę..."
    ERROR = "Błąd!"
    STOPPED = "Zatrzymany"


class BotLogic:
    """Główna klasa logiki bota."""
    
    def __init__(self, status_callback=None):
        """
        Args:
            status_callback: Funkcja do aktualizacji statusu w GUI
        """
        self.status_callback = status_callback
        
        # Komponenty
        self.calibrator = Calibrator()
        self.detector = BlockDetector()
        self.mouse = MouseController()
        self.sequencer = None  # Inicjalizowane po kalibracji
        self.scanner = None    # Inicjalizowane po kalibracji
        self.board = BoardState()
        
        # Stan
        self.state = BotState.IDLE
        self.is_running = False
        self.is_paused = False
        self.should_stop = False
        
        # Statystyki
        self.stats = {
            'boards_completed': 0,
            'blocks_placed': 0,
            'blocks_discarded': 0,
            'current_board_blocks': 0
        }
        
        # Wątek bota
        self.bot_thread = None
        
        # Debug
        self.debug_mode = False
                # Callback dla pustej skrzynki
        self.on_chest_empty = None
    
    def log(self, message):
        """Logowanie z opcjonalnym debug."""
        if self.debug_mode:
            print(f"[BOT] {message}")
    
    def update_status(self, state, message=None):
        """Aktualizuje stan i powiadamia GUI."""
        self.state = state
        status_text = message if message else state.value
        self.log(status_text)
        
        if self.status_callback:
            self.status_callback(status_text, self.stats)
    
    def initialize(self):
        """Inicjalizuje bota - wczytuje kalibrację."""
        # Wymuś przeładowanie danych z pliku JSON
        if not self.calibrator.load_calibration():
            self.update_status(BotState.ERROR, "Brak kalibracji!")
            return False
        
        if not self.calibrator.is_valid():
            self.update_status(BotState.ERROR, "Kalibracja niepełna!")
            return False
        
        # Odśwież komponenty nowymi danymi
        self.sequencer = ActionSequencer(self.mouse, self.calibrator)
        self.scanner = BoardScanner(self.calibrator, self.detector)
        
        # Resetujemy stan planszy
        self.board.reset()
        
        self.update_status(BotState.IDLE, "Gotowy | HOME → Start")
        return True
    
    def start(self):
        """Uruchamia bota w osobnym wątku."""
        if self.is_running:
            self.log("Bot już działa!")
            return
        
        if not self.initialize():
            return
        
        self.is_running = True
        self.is_paused = False
        self.should_stop = False
        
        self.bot_thread = threading.Thread(target=self._main_loop, daemon=True)
        self.bot_thread.start()
    
    def pause(self):
        """Pauzuje/wznawia bota."""
        if not self.is_running:
            return
        
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            self.update_status(BotState.PAUSED, "PAUZA - naciśnij HOME aby wznowić")
        else:
            self.update_status(BotState.RUNNING, "Wznawiam...")
            # Przy wznowieniu skanuj planszę
            self._scan_and_update_board()
    
    def stop(self):
        """Zatrzymuje bota."""
        self.should_stop = True
        self.is_running = False
        self.is_paused = False
        self.update_status(BotState.STOPPED, "Zatrzymano")
    
    def _wait_while_paused(self):
        """Czeka gdy bot jest w pauzie."""
        while self.is_paused and not self.should_stop:
            time.sleep(0.1)
    
    def _scan_and_update_board(self):
        """Skanuje planszę i aktualizuje stan."""
        self.log("Skanuję planszę...")
        scanned = self.scanner.scan_board()
        self.board.update_from_scan(scanned)
        self.log(f"Stan: {self.board.get_total_placed()}/7 klocków")
    
    def _fetch_block(self):
        """
        Pobiera klocek ze skrzynki.
        
        Returns:
            str: Typ klocka lub None jeśli nie udało się pobrać
        """
        self.update_status(BotState.FETCHING)
        
        retries = 0
        
        while retries < MAX_CHEST_RETRIES:
            # Kliknij skrzynkę i jedź na parking
            self.sequencer.fetch_new_block()
            
            # Poczekaj na ustabilizowanie
            time.sleep(DELAYS['detection_wait'])
            
            # Rozpoznaj klocek NA PARKINGU (nie gdzie indziej!)
            self.update_status(BotState.DETECTING)
            parking_x, parking_y = self.calibrator.get_parking_position()
            block_type = self.detector.detect_block_at_position(parking_x, parking_y)
            
            if block_type is not None:
                self.log(f"Rozpoznano: {block_type}")
                return block_type
            
            retries += 1
            self.log(f"Nie wykryto klocka, próba {retries}/{MAX_CHEST_RETRIES}")
            time.sleep(DELAYS['retry_delay'])
        
        # Nie udało się pobrać klocka
        self.log("Masz jeszcze")
        
        # Wywołaj callback dla pustej skrzynki (dźwięk)
        if self.on_chest_empty:
            self.on_chest_empty()
        
        return None
    
    def _place_block(self, block_type):
        """
        Umieszcza klocek na planszy.
        
        Args:
            block_type: Typ klocka do położenia
            
        Returns:
            bool: True jeśli położono, False jeśli odrzucono
        """
        # Sprawdź czy możemy położyć ten typ
        if not self.board.can_place_block(block_type):
            self.log(f"Nie można położyć {block_type} - limit osiągnięty lub brak miejsca")
            return False
        
        # Znajdź wolną pozycję
        position = self.board.get_next_position(block_type)
        
        if position is None:
            self.log(f"Brak wolnej pozycji dla {block_type}")
            return False
        
        # Połóż klocek
        self.update_status(BotState.PLACING, f"Kładę {block_type} na {position['id']}...")
        
        self.sequencer.place_block_at_position(
            position['center_col'],
            position['center_row']
        )
        
        # Zaktualizuj stan planszy
        self.board.mark_position_used(block_type, position)
        
        # Statystyki
        self.stats['blocks_placed'] += 1
        self.stats['current_board_blocks'] += 1
        
        self.log(f"Położono {block_type} na {position['id']} - {self.board.get_total_placed()}/7")
        
        return True
    
    def _discard_block(self, block_type):
        """
        Odrzuca klocek.
        
        Args:
            block_type: Typ klocka (do logowania)
        """
        self.update_status(BotState.DISCARDING, f"Odrzucam {block_type}...")
        
        self.sequencer.discard_current_block()
        
        self.stats['blocks_discarded'] += 1
        self.log(f"Odrzucono {block_type}")
    
    def _complete_board(self):
        """Kończy planszę - klika OK."""
        self.update_status(BotState.COMPLETING, "Plansza ukończona!")
        
        # Poczekaj na pojawienie się okna z nagrodą
        time.sleep(0.5)
        
        # Kliknij OK
        self.sequencer.confirm_completion()
        
        # Statystyki
        self.stats['boards_completed'] += 1
        self.stats['current_board_blocks'] = 0
        
        # Reset planszy
        self.board.reset()
        
        self.log(f"Ukończono planszę #{self.stats['boards_completed']}")
        
        # Poczekaj na nową planszę
        time.sleep(0.5)
    
    def _main_loop(self):
        """Główna pętla bota."""
        self.update_status(BotState.RUNNING, "Rozpoczynam...")
        
        # Początkowy skan planszy
        self._scan_and_update_board()
        
        while self.is_running and not self.should_stop:
            # Sprawdź pauzę
            self._wait_while_paused()
            if self.should_stop:
                break
            
            # Sprawdź czy plansza ukończona
            if self.board.is_complete():
                self._complete_board()
                continue
            
            # Pobierz klocek
            block_type = self._fetch_block()
            
            if block_type is None:
                # Nie udało się pobrać - pauza
                self.is_paused = True
                self.update_status(BotState.PAUSED, 
                    "Wymień skrzynkę i naciśnij HOME")
                continue
            
            # Sprawdź czy położyć czy odrzucić
            if block_type == 'ORANGE':
                # ORANGE zawsze odrzucamy
                self._discard_block(block_type)
            elif self.board.can_place_block(block_type):
                # Próbuj położyć
                placed = self._place_block(block_type)
                if not placed:
                    self._discard_block(block_type)
            else:
                # Limit osiągnięty - odrzuć
                self._discard_block(block_type)
            
            # Krótka pauza przed następną iteracją
            time.sleep(0.05)
        
        self.update_status(BotState.STOPPED, "Zatrzymano")
        self.is_running = False


# =============================================================================
# TEST MODUŁU
# =============================================================================
if __name__ == "__main__":
    import keyboard
    
    print("=== TEST BOT LOGIC ===\n")
    
    def status_callback(status, stats):
        print(f"[STATUS] {status}")
        print(f"         Plansze: {stats['boards_completed']} | "
              f"Położone: {stats['blocks_placed']} | "
              f"Odrzucone: {stats['blocks_discarded']}")
    
    bot = BotLogic(status_callback=status_callback)
    bot.debug_mode = True
    
    print("Inicjalizacja...")
    if not bot.initialize():
        print("Błąd inicjalizacji!")
        exit(1)
    
    print("\nSterowanie:")
    print("  HOME = Start")
    print("  END  = Pauza/Wznów")
    print("  ESC  = Stop i wyjście")
    print()
    
    def on_home():
        if not bot.is_running:
            print("\n>>> START <<<")
            bot.start()
    
    def on_end():
        if bot.is_running:
            print("\n>>> PAUZA/WZNÓW <<<")
            bot.pause()
    
    def on_escape():
        print("\n>>> STOP <<<")
        bot.stop()
    
    keyboard.on_press_key('home', lambda _: on_home())
    keyboard.on_press_key('end', lambda _: on_end())
    
    print("Czekam na HOME aby rozpocząć...")
    keyboard.wait('escape')
    
    bot.stop()
    keyboard.unhook_all()
    
    print("\n=== STATYSTYKI KOŃCOWE ===")
    print(f"Ukończone plansze: {bot.stats['boards_completed']}")
    print(f"Położone klocki:   {bot.stats['blocks_placed']}")
    print(f"Odrzucone klocki:  {bot.stats['blocks_discarded']}")