"""
Block Solver - Board State Module
Moduł do zarządzania stanem planszy i znajdowania wolnych pozycji.
"""

from config import BOARD_ROWS, BOARD_COLS, BLOCK_POSITIONS, BLOCK_LIMITS


class BoardState:
    """Klasa zarządzająca stanem planszy."""
    
    def __init__(self):
        # Macierz 4x6 - None = puste, string = typ klocka
        self.grid = [[None for _ in range(BOARD_COLS)] for _ in range(BOARD_ROWS)]
        
        # Licznik umieszczonych klocków każdego typu
        self.placed_counts = {block_type: 0 for block_type in BLOCK_LIMITS.keys()}
        
        # Które pozycje zostały już zajęte (np. 'R1', 'R2')
        self.used_positions = set()
    
    def reset(self):
        """Resetuje planszę do stanu początkowego."""
        self.grid = [[None for _ in range(BOARD_COLS)] for _ in range(BOARD_ROWS)]
        self.placed_counts = {block_type: 0 for block_type in BLOCK_LIMITS.keys()}
        self.used_positions = set()
    
    def update_from_scan(self, scanned_grid):
        """
        Aktualizuje stan na podstawie skanu planszy.
        """
        self.grid = [row[:] for row in scanned_grid]  # Kopia
        
        # Przelicz ile pól zajmuje każdy typ klocka na planszy
        cell_counts = {block_type: 0 for block_type in BLOCK_LIMITS.keys()}
        
        for row in self.grid:
            for cell in row:
                if cell is not None and cell in cell_counts:
                    cell_counts[cell] += 1
        
        # Przelicz na SZTUKI klocków (dzieląc przez rozmiar klocka)
        # CYAN: 4 kratki, BLUE: 3, RED: 4, GREEN: 3, YELLOW: 3
        sizes = {'CYAN': 4, 'BLUE': 3, 'RED': 4, 'GREEN': 3, 'YELLOW': 3, 'ORANGE': 1}
        
        for block_type in cell_counts:
            size = sizes.get(block_type, 1)
            # Dzielenie z zaokrągleniem w górę, żeby nawet 1 kratka liczyła się jako 1 klocek
            self.placed_counts[block_type] = (cell_counts[block_type] + size - 1) // size
    
    def can_place_block(self, block_type):
        """
        Sprawdza czy można umieścić klocek danego typu.
        
        Returns:
            bool: True jeśli jest wolna pozycja dla tego typu
        """
        limit = BLOCK_LIMITS.get(block_type, 0)
        current = self.placed_counts.get(block_type, 0)
        
        return current < limit
    
    def get_next_position(self, block_type):
        """
        Zwraca następną wolną pozycję dla danego typu klocka.
        
        Returns:
            dict: Pozycja {'id': 'R1', 'center_col': 1.5, 'center_row': 1.0, 'cells': [...]}
            None: Jeśli brak wolnych pozycji
        """
        positions = BLOCK_POSITIONS.get(block_type, [])
        
        for pos in positions:
            pos_id = pos['id']
            
            # Sprawdź czy ta pozycja już została użyta
            if pos_id in self.used_positions:
                continue
            
            # Sprawdź czy wszystkie kratki są wolne
            all_free = True
            for (row, col) in pos['cells']:
                if self.grid[row][col] is not None:
                    all_free = False
                    break
            
            if all_free:
                return pos
        
        return None
    
    def mark_position_used(self, block_type, position):
        """
        Oznacza pozycję jako zajętą po umieszczeniu klocka.
        
        Args:
            block_type: Typ klocka (np. 'RED')
            position: Słownik pozycji z get_next_position()
        """
        # Oznacz kratki na planszy
        for (row, col) in position['cells']:
            self.grid[row][col] = block_type
        
        # Zwiększ licznik
        self.placed_counts[block_type] = self.placed_counts.get(block_type, 0) + 1
        
        # Oznacz pozycję jako użytą
        self.used_positions.add(position['id'])
    
    def get_total_placed(self):
        """Zwraca łączną liczbę umieszczonych klocków."""
        return sum(self.placed_counts.values())
    
    def is_complete(self):
        """Sprawdza czy plansza jest ukończona (7 klocków)."""
        return self.get_total_placed() >= 7
    
    def get_empty_count(self):
        """Zwraca liczbę pustych kratek."""
        count = 0
        for row in self.grid:
            for cell in row:
                if cell is None:
                    count += 1
        return count
    
    def print_state(self):
        """Wyświetla aktualny stan planszy."""
        print("\n=== STAN PLANSZY ===")
        print("    ", end="")
        for col in range(BOARD_COLS):
            print(f" {col}  ", end="")
        print()
        
        for row_idx, row in enumerate(self.grid):
            print(f" {row_idx}: ", end="")
            for cell in row:
                if cell is None:
                    print(" .  ", end="")
                else:
                    print(f" {cell[0]}  ", end="")
            print()
        
        print(f"\nUmieszczono: {self.get_total_placed()}/7 klocków")
        print(f"Puste kratki: {self.get_empty_count()}/24")
        print(f"Użyte pozycje: {self.used_positions}")
    
    def get_status_text(self):
        """Zwraca tekstowy status do GUI."""
        placed = self.get_total_placed()
        return f"Klocki: {placed}/7 | Puste: {self.get_empty_count()}/24"


# =============================================================================
# TEST MODUŁU
# =============================================================================
if __name__ == "__main__":
    print("=== TEST MODUŁU BOARD STATE ===\n")
    
    board = BoardState()
    
    print("1. Pusta plansza:")
    board.print_state()
    
    print("\n2. Test umieszczania klocków:")
    
    # Sprawdź czy można położyć RED
    if board.can_place_block('RED'):
        pos = board.get_next_position('RED')
        if pos:
            print(f"\nMożna położyć RED na pozycji {pos['id']}")
            print(f"  Środek: ({pos['center_col']}, {pos['center_row']})")
            print(f"  Kratki: {pos['cells']}")
            
            # Symuluj położenie
            board.mark_position_used('RED', pos)
            print("  -> Położono!")
    
    # Sprawdź następną pozycję dla RED
    if board.can_place_block('RED'):
        pos = board.get_next_position('RED')
        if pos:
            print(f"\nMożna położyć drugi RED na pozycji {pos['id']}")
            board.mark_position_used('RED', pos)
            print("  -> Położono!")
    
    # Sprawdź czy można położyć trzeci RED
    if board.can_place_block('RED'):
        print("\nMożna położyć trzeci RED")
    else:
        print("\nNie można położyć trzeciego RED (limit = 2)")
    
    print("\n3. Stan po umieszczeniu 2x RED:")
    board.print_state()
    
    # Test ORANGE
    print("\n4. Test ORANGE:")
    if board.can_place_block('ORANGE'):
        print("Można położyć ORANGE")
    else:
        print("Nie można położyć ORANGE (limit = 0, zawsze odrzucamy)")
    
    print("\n=== KONIEC TESTU ===")