from neuro_symbolic_vln.env.tasks import (
    make_goto_goal_probe_env,
    make_locked_door_probe_env,
)
from neuro_symbolic_vln.evaluation.oracle import (
    ExactOracle,
    OracleTaskModel,
    model_from_probe_env,
    shortest_primitive_cost,
)


def test_shortest_primitive_cost_counts_turn_and_forward() -> None:
    cost = shortest_primitive_cost(
        start=(1, 1, "north"),
        goal=(2, 1, "east"),
        passable={(1, 1), (2, 1)},
    )
    assert cost == 2  # turn_right + move_forward


def test_shortest_primitive_cost_returns_none_when_unreachable() -> None:
    cost = shortest_primitive_cost(
        start=(1, 1, "north"),
        goal=(5, 5, "east"),
        passable={(1, 1)},
    )
    assert cost is None


def test_key_door_exact_primitive_cost() -> None:
    # Hand-built probe layout: key (2,1), locked red door (3,1),
    # success when the agent's front cell is (4,1).
    model = OracleTaskModel(
        family="key_door_goal",
        start=(1, 1),
        start_heading="east",
        passable=frozenset({(1, 1), (1, 2), (1, 3), (4, 1)}),
        keys=frozenset({((2, 1), "red")}),
        locked_doors=frozenset({((3, 1), "red")}),
        target=(4, 1),
    )

    solution = ExactOracle().solve(model)

    # pickup + forward + toggle + forward, two grid moves.
    assert solution.solvable
    assert solution.optimal_primitive_actions == 4
    assert solution.optimal_grid_distance == 2


def test_key_door_with_wrong_key_is_unsolvable() -> None:
    model = OracleTaskModel(
        family="key_door_goal",
        start=(1, 1),
        start_heading="east",
        passable=frozenset({(1, 1), (1, 2), (1, 3), (4, 1)}),
        keys=frozenset({((2, 1), "blue")}),
        locked_doors=frozenset({((3, 1), "red")}),
        target=(4, 1),
    )

    solution = ExactOracle().solve(model)

    assert not solution.solvable
    assert solution.optimal_primitive_actions is None
    assert solution.optimal_grid_distance is None


def test_goto_exact_cost_from_real_probe_env() -> None:
    env = make_goto_goal_probe_env(target_color="green", agent_dir=0)
    env.reset(seed=0)

    solution = ExactOracle().solve(
        model_from_probe_env(env, "goto_type_color", (3, 1))
    )

    # Agent at (1,1) facing east: one forward puts the ball in front.
    assert solution.solvable
    assert solution.optimal_primitive_actions == 1
    assert solution.optimal_grid_distance == 1


def test_key_door_exact_cost_from_real_probe_env() -> None:
    env = make_locked_door_probe_env(agent_dir=1)  # start facing south
    env.reset(seed=0)

    solution = ExactOracle().solve(
        model_from_probe_env(env, "key_door_goal", (4, 1))
    )

    # Turn to east (1), pickup (1), forward (1), toggle (1), forward (1).
    assert solution.solvable
    assert solution.optimal_primitive_actions == 5
    assert solution.optimal_grid_distance == 2

def test_goto_requires_target_in_front_not_same_position() -> None:
    model = OracleTaskModel(
        family="goto_type_color",
        start=(2, 1),
        start_heading="north",
        passable=frozenset({(2, 1)}),
        keys=frozenset(),
        locked_doors=frozenset(),
        target=(2, 1),
    )

    solution = ExactOracle().solve(model)

    assert not solution.solvable

def test_key_door_requires_pickup_before_forward() -> None:
    model = OracleTaskModel(
        family="key_door_goal",
        start=(1, 1),
        start_heading="east",
        passable=frozenset({(1, 1), (2, 1), (3, 1)}),
        keys=frozenset({((2, 1), "red")}),
        locked_doors=frozenset(),
        target=(3, 1),
    )

    solution = ExactOracle().solve(model)

    assert solution.solvable
    assert solution.optimal_primitive_actions == 1
    assert solution.optimal_grid_distance == 1

def test_key_door_requires_pickup_before_forward_2() -> None:
    model = OracleTaskModel(
        family="key_door_goal",
        start=(1, 1),
        start_heading="east",
        passable=frozenset({(1, 1), (2, 1), (4, 1)}),
        keys=frozenset({((2, 1), "red")}),
        locked_doors=frozenset({((3, 1), "red")}),
        target=(4, 1),
    )

    solution = ExactOracle().solve(model)

    assert solution.solvable
    assert solution.optimal_primitive_actions == 4
    assert solution.optimal_grid_distance == 2

def test_shortest_path() -> None:
    model = OracleTaskModel(
            family="key_door_goal",
            start=(0, 0),
            start_heading="east",
            passable=frozenset({(0,0), (0,1), (0, 2), (0,3), (0,4),
                                (1,0), (1,1),         (1,3),
                                (2,0), (2,1),
                                (3,0), (3,1), (3, 2), (3,3), (3,4),
                                              (4, 2), (4,3), (4,4),
                                (5,0), (5,1), (5, 2)
                                }),
            keys=frozenset({((1, 3), "red")}),
            locked_doors=frozenset({((4, 0), "red")}),
            target=(5, 0),
        )
    solution = ExactOracle().solve(model)
    assert solution.solvable
    assert solution.optimal_primitive_actions == 11
    assert solution.optimal_grid_distance == 8

def test_chooses_lower_primitive_cost_path() -> None:
    model = OracleTaskModel(
        family="simple",
        start=(0, 0),
        start_heading="east",
        passable=frozenset({
            (0, 0), (0, 1), (0, 2),
            (1, 0),         (1, 2),
            (2, 0),                 (2, 2),
            (3, 0),                 (3, 2),
        }),
        keys=frozenset(),
        locked_doors=frozenset(),
        target=(3, 0),
    )

    solution = ExactOracle().solve(model)

    assert solution.solvable
    assert solution.optimal_grid_distance == 2
    assert solution.optimal_primitive_actions == 2

def test_avoids_or_recovers_from_dead_end() -> None:
    model = OracleTaskModel(
        family="simple",
        start=(0, 0),
        start_heading="east",
        passable=frozenset({
            (0, 0),
            (1, 0),
            (2, 0),
            (2, 1),
            (2, 2),
            (1, 2),
            (0, 2),
        }),
        keys=frozenset(),
        locked_doors=frozenset(),
        target=(0, 2),
    )

    solution = ExactOracle().solve(model)

    assert solution.solvable

def test_room_in_room() -> None:
    model = OracleTaskModel(
        family="",
        start=(0,0),
        start_heading="east",
        passable = frozenset({
            (0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0),
            (0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1),
            (0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2),
            (0, 3), (1, 3), (2, 3),                         (6, 3),
            (0, 4), (1, 4), (2, 4),         (4, 4),         (6, 4),
            (0, 5), (1, 5), (2, 5),                         (6, 5),
            (0, 6), (1, 6), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6),
            }),
        keys=frozenset({((0, 5), "red")}),
        locked_doors=frozenset({((3, 4), "red")}),
        target=(4, 4),
        )

    solution = ExactOracle().solve(model)

    assert solution.solvable
    assert solution.optimal_grid_distance == 7
    assert solution.optimal_primitive_actions == 11

def test_reverse_direction_requires_two_turns() -> None:
    model = OracleTaskModel(
        family="test",
        start=(2, 0),
        start_heading="east",
        passable=frozenset({
            (0, 0), (1, 0), (2, 0),
        }),
        keys=frozenset(),
        locked_doors=frozenset(),
        target=(0, 0),
    )

    solution = ExactOracle().solve(model)

    assert solution.solvable
    assert solution.optimal_grid_distance == 1
    assert solution.optimal_primitive_actions == 3
