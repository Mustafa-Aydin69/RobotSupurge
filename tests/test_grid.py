"""Grid (environment.Grid) testleri."""

import itertools
import unittest

from environment import MAX_GRID_SIZE, MOVE_DELTAS, Action, Grid

ALL_SIZES = [
    (rows, cols)
    for rows, cols in itertools.product(range(1, MAX_GRID_SIZE + 1), repeat=2)
    if rows * cols >= 2
]


class GridValidationTests(unittest.TestCase):
    def test_all_sizes_from_1x2_to_6x6_are_valid(self):
        self.assertEqual(len(ALL_SIZES), 35)  # 36 boyuttan yalnızca 1×1 geçersiz
        for rows, cols in ALL_SIZES:
            grid = Grid(rows, cols)
            self.assertEqual(len(grid.rooms), rows * cols)
            self.assertEqual(len(set(grid.rooms)), rows * cols, "Oda adları benzersiz olmalı")

    def test_1x1_is_rejected(self):
        with self.assertRaises(ValueError):
            Grid(1, 1)

    def test_out_of_range_sizes_are_rejected(self):
        for rows, cols in [(0, 2), (2, 0), (7, 2), (2, 7), (-1, 3)]:
            with self.subTest(rows=rows, cols=cols), self.assertRaises(ValueError):
                Grid(rows, cols)

    def test_non_integer_sizes_are_rejected(self):
        for rows, cols in [("2", 2), (2.0, 2), (True, 2)]:
            with self.subTest(rows=rows, cols=cols), self.assertRaises(ValueError):
                Grid(rows, cols)

    def test_grid_is_immutable(self):
        grid = Grid(3, 3)
        with self.assertRaises(AttributeError):
            grid.rows = 4
        with self.assertRaises(AttributeError):
            grid.rooms = ()
        self.assertIsInstance(grid.rooms, tuple)

    def test_copy_and_pickle_preserve_grid(self):
        import copy
        import pickle
        grid = Grid(3, 4)
        self.assertIs(copy.copy(grid), grid)
        self.assertIs(copy.deepcopy(grid), grid)
        self.assertEqual(pickle.loads(pickle.dumps(grid)), grid)

    def test_equality(self):
        self.assertEqual(Grid(2, 3), Grid(2, 3))
        self.assertNotEqual(Grid(2, 3), Grid(3, 2))


class GridNamingTests(unittest.TestCase):
    def test_1x2_uses_a_and_b(self):
        grid = Grid(1, 2)
        self.assertTrue(grid.is_two_room)
        self.assertEqual(grid.rooms, ("A", "B"))

    def test_other_grids_use_row_letter_and_column_number(self):
        self.assertEqual(Grid(2, 2).rooms, ("A1", "A2", "B1", "B2"))
        self.assertEqual(Grid(1, 3).rooms, ("A1", "A2", "A3"))
        self.assertEqual(Grid(2, 1).rooms, ("A1", "B1"))
        self.assertFalse(Grid(2, 1).is_two_room)
        self.assertEqual(Grid(6, 6).rooms[-1], "F6")

    def test_name_and_position_round_trip(self):
        for rows, cols in ALL_SIZES:
            grid = Grid(rows, cols)
            for row, col in itertools.product(range(rows), range(cols)):
                name = grid.name_of(row, col)
                self.assertEqual(grid.position_of(name), (row, col))

    def test_position_examples(self):
        grid = Grid(3, 4)
        self.assertEqual(grid.position_of("A1"), (0, 0))
        self.assertEqual(grid.position_of("B3"), (1, 2))
        self.assertEqual(grid.position_of("C4"), (2, 3))
        self.assertEqual(Grid(1, 2).position_of("B"), (0, 1))

    def test_unknown_room_is_rejected(self):
        with self.assertRaises(ValueError):
            Grid(2, 2).position_of("C1")
        with self.assertRaises(ValueError):
            Grid(2, 2).name_of(2, 0)


class GridMoveTests(unittest.TestCase):
    def test_valid_moves_examples(self):
        grid = Grid(3, 3)
        L, R, U, D = Action.LEFT, Action.RIGHT, Action.UP, Action.DOWN
        self.assertEqual(set(grid.valid_moves("A1")), {R, D})          # sol üst köşe
        self.assertEqual(set(grid.valid_moves("C3")), {L, U})          # sağ alt köşe
        self.assertEqual(set(grid.valid_moves("A2")), {L, R, D})       # üst kenar
        self.assertEqual(set(grid.valid_moves("B2")), {L, R, U, D})    # orta
        self.assertEqual(Grid(1, 2).valid_moves("A"), (R,))
        self.assertEqual(Grid(1, 2).valid_moves("B"), (L,))
        self.assertEqual(Grid(2, 1).valid_moves("A1"), (D,))

    def test_neighbor_examples(self):
        grid = Grid(3, 4)
        self.assertEqual(grid.neighbor("B2", Action.UP), "A2")
        self.assertEqual(grid.neighbor("B2", Action.DOWN), "C2")
        self.assertEqual(grid.neighbor("B2", Action.LEFT), "B1")
        self.assertEqual(grid.neighbor("B2", Action.RIGHT), "B3")

    def test_every_move_in_every_grid_matches_bounds(self):
        """35 grid boyutunda her oda ve her yön için tam tarama."""
        checked = 0
        for rows, cols in ALL_SIZES:
            grid = Grid(rows, cols)
            for name in grid.rooms:
                row, col = grid.position_of(name)
                for action, (d_row, d_col) in MOVE_DELTAS.items():
                    inside = 0 <= row + d_row < rows and 0 <= col + d_col < cols
                    self.assertEqual(action in grid.valid_moves(name), inside)
                    if inside:
                        self.assertEqual(grid.neighbor(name, action), grid.name_of(row + d_row, col + d_col))
                    else:
                        with self.assertRaises(ValueError):
                            grid.neighbor(name, action)
                    checked += 1
        self.assertEqual(checked, 4 * sum(r * c for r, c in ALL_SIZES))

    def test_clean_is_not_a_move(self):
        with self.assertRaises(ValueError):
            Grid(2, 2).neighbor("A1", Action.CLEAN)


if __name__ == "__main__":
    unittest.main()
