"""Click-to-build map editor used by :mod:`pygame_demo`."""

from __future__ import annotations

import json

import pygame
import pygame_demo
from pygame_demo import (
    ACCENT,
    BG,
    ERROR,
    MUTED,
    PANEL,
    TEXT,
    _draw_grid,
    _record_custom_episode,
    _text,
)

from neuro_symbolic_vln.env.custom_map import CustomMapSpec

WINDOW = (2288, 1287)
COLORS = {
    "red": (224, 81, 91),
    "green": (61, 188, 113),
    "blue": (87, 160, 255),
    "yellow": (228, 191, 73),
}
TOOLS = ("wall", "key", "door", "goal", "ball", "robot")


def _map_code(
    width: int,
    height: int,
    cells: dict[tuple[int, int], tuple[str, str]],
    robot: tuple[int, int],
    direction: int,
) -> str:
    """Return a portable, human-editable representation of a custom map."""
    objects = [
        {"type": kind, "color": color, "x": x, "y": y}
        for (x, y), (kind, color) in sorted(cells.items())
    ]
    return json.dumps(
        {
            "width": width,
            "height": height,
            "robot": {"x": robot[0], "y": robot[1], "direction": direction},
            "objects": objects,
        },
        indent=2,
    )


def _load_map_code(
    text: str,
) -> tuple[int, int, dict[tuple[int, int], tuple[str, str]], tuple[int, int], int]:
    """Parse and validate map code before it changes the editor state."""
    try:
        payload = json.loads(text)
        width, height = int(payload["width"]), int(payload["height"])
        robot_data = payload["robot"]
        robot = (int(robot_data["x"]), int(robot_data["y"]))
        direction = int(robot_data["direction"])
        cells = {
            (int(item["x"]), int(item["y"])): (str(item["type"]), str(item["color"]))
            for item in payload["objects"]
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid map code: {error}") from error
    if any(
        kind not in {"wall", "key", "door", "goal", "ball"}
        for kind, _ in cells.values()
    ):
        raise ValueError("Map code contains an unsupported object type.")
    spec = CustomMapSpec(width, height, cells, robot, direction)
    if problem := spec.validate():
        raise ValueError(problem)
    return width, height, cells, robot, direction


def _cursor_from_point(
    text: str,
    area: pygame.Rect,
    point: tuple[int, int],
    font: pygame.font.Font,
    scroll_lines: int = 0,
) -> int:
    lines = text.splitlines(keepends=True) or [""]
    line_index = min(
        len(lines) - 1,
        scroll_lines + max(0, (point[1] - area.y - 14) // 22),
    )
    line_start = sum(len(line) for line in lines[:line_index])
    raw_line = lines[line_index].rstrip("\n")
    target_x = point[0] - area.x - 16
    column = 0
    while column < len(raw_line) and font.size(raw_line[: column + 1])[0] <= target_x:
        column += 1
    return line_start + column


def _draw_icon(
    surface: pygame.Surface,
    rect: pygame.Rect,
    kind: str,
    color: tuple[int, int, int],
    direction: int = 0,
) -> None:
    """Draw recognisable icons that remain proportional at every cell size."""
    cx, cy = rect.center
    unit = max(3, min(rect.width, rect.height) // 4)
    if kind == "key":
        pygame.draw.circle(surface, color, (cx - unit, cy - unit), unit)
        pygame.draw.circle(surface, BG, (cx - unit, cy - unit), max(1, unit // 2))
        pygame.draw.rect(
            surface, color, (cx, cy - unit // 3, unit * 2, max(2, unit // 2))
        )
        pygame.draw.rect(surface, color, (cx + unit, cy, max(2, unit // 2), unit))
    elif kind == "goal":
        pygame.draw.circle(
            surface, (255, 209, 79), (cx, cy), unit * 2, width=max(2, unit // 2)
        )
        pygame.draw.circle(surface, (255, 209, 79), (cx, cy), max(2, unit // 2))
        pygame.draw.line(
            surface,
            (255, 209, 79),
            (cx, cy - unit * 2),
            (cx, cy + unit * 2),
            width=max(2, unit // 3),
        )
    elif kind == "robot":
        delta = ((1, 0), (0, 1), (-1, 0), (0, -1))[direction]
        side = (-delta[1], delta[0])
        tip = (cx + delta[0] * unit * 2, cy + delta[1] * unit * 2)
        left = (
            cx + side[0] * unit - delta[0] * unit,
            cy + side[1] * unit - delta[1] * unit,
        )
        right = (
            cx - side[0] * unit - delta[0] * unit,
            cy - side[1] * unit - delta[1] * unit,
        )
        pygame.draw.polygon(surface, (87, 188, 255), [tip, left, right])
        pygame.draw.circle(surface, TEXT, (cx, cy), max(2, unit // 3))
    elif kind == "ball":
        pygame.draw.circle(surface, color, (cx, cy), unit * 2)
        pygame.draw.circle(
            surface, TEXT, (cx - unit // 2, cy - unit // 2), max(1, unit // 3)
        )


def run_custom_editor() -> int:
    pygame.init()
    screen = pygame.display.set_mode(WINDOW)
    pygame.display.set_caption("NeuSym-Nav | custom map editor")
    title = pygame.font.SysFont("sans", 34, bold=True)
    body = pygame.font.SysFont("sans", 22)
    small = pygame.font.SysFont("sans", 17)
    clock = pygame.time.Clock()
    width, height = 10, 8
    cells: dict[tuple[int, int], tuple[str, str]] = {}
    robot, direction = (1, 1), 0
    tool, color = "wall", "red"
    instruction = "pick up the red key, open the red door, then go to the goal"
    active, snapshots, index, last = True, [], 0, 0
    status = "Build a map, then press Start. Boundary cells are walls."
    code_visible = False
    code_text = ""
    code_cursor = 0
    code_anchor: int | None = None
    code_dragging = False
    code_scroll_line = 0
    code_scroll_dragging = False
    running = True

    def replace_selection(value: str) -> None:
        nonlocal code_anchor, code_cursor, code_text
        if code_anchor is not None:
            selection_start, selection_end = sorted((code_anchor, code_cursor))
            code_text = code_text[:selection_start] + value + code_text[selection_end:]
            code_cursor = selection_start + len(value)
            code_anchor = None
        else:
            code_text = code_text[:code_cursor] + value + code_text[code_cursor:]
            code_cursor += len(value)

    while running:
        screen_width, screen_height = screen.get_size()
        map_canvas = pygame.Rect(50, 210, int(screen_width * 0.60), screen_height - 355)
        sidebar = pygame.Rect(
            map_canvas.right + 35,
            210,
            screen_width - map_canvas.right - 85,
            screen_height - 295,
        )
        cell = max(12, min(map_canvas.width // width, map_canvas.height // height))
        origin = (
            map_canvas.x + (map_canvas.width - width * cell) // 2,
            map_canvas.y + (map_canvas.height - height * cell) // 2,
        )
        grid_rect = pygame.Rect(origin[0], origin[1], width * cell, height * cell)
        input_box = pygame.Rect(50, 120, screen_width - 780, 52)
        start_button = pygame.Rect(input_box.right + 25, 120, 160, 52)
        replay = pygame.Rect(start_button.right + 25, 120, 170, 52)
        reset = pygame.Rect(replay.right + 25, 120, 190, 52)
        back = pygame.Rect(screen_width - 210, 30, 160, 46)
        tool_rects = {
            value: pygame.Rect(
                sidebar.x + 30, sidebar.y + 70 + pos * 52, sidebar.width // 2 - 50, 42
            )
            for pos, value in enumerate(TOOLS)
        }
        color_rects = {
            value: pygame.Rect(
                sidebar.centerx + 10,
                sidebar.y + 70 + pos * 52,
                sidebar.width // 2 - 40,
                42,
            )
            for pos, value in enumerate(COLORS)
        }
        size_buttons = {
            "w-": pygame.Rect(map_canvas.x, map_canvas.bottom + 25, 46, 38),
            "w+": pygame.Rect(map_canvas.x + 210, map_canvas.bottom + 25, 46, 38),
            "h-": pygame.Rect(map_canvas.x + 320, map_canvas.bottom + 25, 46, 38),
            "h+": pygame.Rect(map_canvas.x + 530, map_canvas.bottom + 25, 46, 38),
        }
        direction_y = sidebar.y + 410
        direction_buttons = [
            pygame.Rect(sidebar.x + 30 + n * 70, direction_y, 58, 42) for n in range(4)
        ]
        examples = [
            pygame.Rect(sidebar.x + 30, direction_y + 75, sidebar.width - 60, 42),
            pygame.Rect(sidebar.x + 30, direction_y + 128, sidebar.width - 60, 55),
        ]
        code_button = pygame.Rect(
            sidebar.x + 30, sidebar.bottom - 68, sidebar.width - 60, 42
        )
        modal = pygame.Rect(140, 190, screen_width - 280, screen_height - 300)
        code_area = pygame.Rect(
            modal.x + 28, modal.y + 105, modal.width - 56, modal.height - 195
        )
        import_button = pygame.Rect(modal.right - 220, modal.bottom - 70, 190, 42)
        line_count = len(code_text.splitlines()) or 1
        visible_line_count = max(1, (code_area.height - 28) // 22)
        max_scroll = max(0, line_count - visible_line_count)
        code_scroll_line = min(code_scroll_line, max_scroll)
        scroll_track = pygame.Rect(
            code_area.right - 13, code_area.y + 4, 9, code_area.height - 8
        )
        thumb_height = max(24, scroll_track.height * visible_line_count // line_count)
        thumb_range = max(1, scroll_track.height - thumb_height)
        thumb_offset = (
            0 if not max_scroll else thumb_range * code_scroll_line // max_scroll
        )
        scroll_thumb = pygame.Rect(
            scroll_track.x,
            scroll_track.y + thumb_offset,
            scroll_track.width,
            thumb_height,
        )
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                point = event.pos
                if code_visible:
                    if event.button in {4, 5} and max_scroll:
                        code_scroll_line = max(
                            0,
                            min(
                                max_scroll,
                                code_scroll_line + (1 if event.button == 5 else -1),
                            ),
                        )
                        if code_dragging:
                            code_cursor = _cursor_from_point(
                                code_text,
                                code_area,
                                pygame.mouse.get_pos(),
                                small,
                                code_scroll_line,
                            )
                    elif scroll_thumb.collidepoint(point) and max_scroll:
                        code_scroll_dragging = True
                    elif scroll_track.collidepoint(point) and max_scroll:
                        ratio = (
                            point[1] - scroll_track.y - thumb_height // 2
                        ) / thumb_range
                        code_scroll_line = round(max_scroll * max(0.0, min(1.0, ratio)))
                    elif import_button.collidepoint(point):
                        try:
                            width, height, cells, robot, direction = _load_map_code(
                                code_text
                            )
                            snapshots = []
                            status = "Map code imported."
                            code_visible = False
                        except ValueError as error:
                            status = str(error)
                    elif code_area.collidepoint(point):
                        code_cursor = _cursor_from_point(
                            code_text, code_area, point, small, code_scroll_line
                        )
                        code_anchor = code_cursor
                        code_dragging = True
                    elif not modal.collidepoint(point):
                        code_visible = False
                    continue
                if input_box.collidepoint(point):
                    active = True
                elif start_button.collidepoint(point):
                    spec = CustomMapSpec(width, height, cells, robot, direction)
                    snapshots, status = _record_custom_episode(spec, instruction)
                    index, last = 0, now
                elif replay.collidepoint(point):
                    spec = CustomMapSpec(width, height, cells, robot, direction)
                    snapshots, status = _record_custom_episode(spec, instruction)
                    index, last = 0, now
                elif reset.collidepoint(point):
                    cells, robot, direction, snapshots = {}, (1, 1), 0, []
                    status = "Map reset."
                elif back.collidepoint(point):
                    pygame.quit()
                    return 1
                elif code_button.collidepoint(point):
                    code_text = _map_code(width, height, cells, robot, direction)
                    code_cursor = len(code_text)
                    code_anchor = None
                    code_scroll_line = 0
                    code_visible = True
                elif grid_rect.collidepoint(point):
                    x, y = (
                        (point[0] - origin[0]) // cell,
                        (point[1] - origin[1]) // cell,
                    )
                    if 0 < x < width - 1 and 0 < y < height - 1:
                        snapshots = []
                        if tool == "robot":
                            if (x, y) not in cells:
                                robot = (x, y)
                        elif (x, y) != robot:
                            current = cells.get((x, y))
                            if current is not None and current[0] == tool:
                                cells.pop((x, y))
                            else:
                                cells[(x, y)] = (tool, color)
                elif any(rect.collidepoint(point) for rect in tool_rects.values()):
                    tool = next(
                        name
                        for name, rect in tool_rects.items()
                        if rect.collidepoint(point)
                    )
                elif any(rect.collidepoint(point) for rect in color_rects.values()):
                    color = next(
                        name
                        for name, rect in color_rects.items()
                        if rect.collidepoint(point)
                    )
                elif any(rect.collidepoint(point) for rect in direction_buttons):
                    direction = next(
                        i
                        for i, rect in enumerate(direction_buttons)
                        if rect.collidepoint(point)
                    )
                elif examples[0].collidepoint(point):
                    instruction = "go to the green ball"
                elif examples[1].collidepoint(point):
                    instruction = (
                        "pick up the red key, open the red door, then go to the goal"
                    )
                else:
                    for name, rect in size_buttons.items():
                        if rect.collidepoint(point):
                            if name == "w-":
                                width = max(3, width - 1)
                            if name == "w+":
                                width = min(35, width + 1)
                            if name == "h-":
                                height = max(3, height - 1)
                            if name == "h+":
                                height = min(35, height + 1)
                            cells = {
                                p: item
                                for p, item in cells.items()
                                if p[0] < width - 1 and p[1] < height - 1
                            }
                            robot = (
                                min(robot[0], width - 2),
                                min(robot[1], height - 2),
                            )
            elif event.type == pygame.MOUSEMOTION and code_visible and code_dragging:
                code_cursor = _cursor_from_point(
                    code_text, code_area, event.pos, small, code_scroll_line
                )
            elif (
                event.type == pygame.MOUSEMOTION
                and code_visible
                and code_scroll_dragging
            ):
                ratio = (
                    event.pos[1] - scroll_track.y - thumb_height // 2
                ) / thumb_range
                code_scroll_line = round(max_scroll * max(0.0, min(1.0, ratio)))
            elif event.type == pygame.MOUSEBUTTONUP and code_visible:
                if event.button == 1:
                    code_dragging = False
                    code_scroll_dragging = False
            elif event.type == pygame.MOUSEWHEEL and code_visible:
                line_count = len(code_text.splitlines()) or 1
                visible_lines = max(1, (code_area.height - 28) // 22)
                max_scroll = max(0, line_count - visible_lines)
                if max_scroll:
                    code_scroll_line = max(
                        0, min(max_scroll, code_scroll_line - event.y)
                    )
                    if code_dragging:
                        code_cursor = _cursor_from_point(
                            code_text,
                            code_area,
                            pygame.mouse.get_pos(),
                            small,
                            code_scroll_line,
                        )
            elif event.type == pygame.KEYDOWN and code_visible:
                if event.key == pygame.K_ESCAPE:
                    code_visible = False
                    code_anchor = None
                elif event.key == pygame.K_a and event.mod & pygame.KMOD_CTRL:
                    code_anchor, code_cursor = 0, len(code_text)
                elif event.key == pygame.K_LEFT:
                    code_cursor = max(0, code_cursor - 1)
                    code_anchor = None
                elif event.key == pygame.K_RIGHT:
                    code_cursor = min(len(code_text), code_cursor + 1)
                    code_anchor = None
                elif event.key == pygame.K_HOME:
                    code_cursor = code_text.rfind("\n", 0, code_cursor) + 1
                elif event.key == pygame.K_END:
                    line_end = code_text.find("\n", code_cursor)
                    code_cursor = len(code_text) if line_end < 0 else line_end
                elif event.key == pygame.K_BACKSPACE:
                    if code_anchor is not None:
                        replace_selection("")
                    elif code_cursor > 0:
                        code_text = (
                            code_text[: code_cursor - 1] + code_text[code_cursor:]
                        )
                        code_cursor -= 1
                elif event.key == pygame.K_DELETE:
                    if code_anchor is not None:
                        replace_selection("")
                    else:
                        code_text = (
                            code_text[:code_cursor] + code_text[code_cursor + 1 :]
                        )
                elif event.key == pygame.K_RETURN:
                    replace_selection("\n")
                elif event.unicode and event.unicode.isprintable():
                    replace_selection(event.unicode)
            elif event.type == pygame.KEYDOWN and active:
                if event.key == pygame.K_RETURN:
                    spec = CustomMapSpec(width, height, cells, robot, direction)
                    snapshots, status = _record_custom_episode(spec, instruction)
                    index, last = 0, now
                elif event.key == pygame.K_BACKSPACE:
                    instruction = instruction[:-1]
                elif event.unicode and event.unicode.isprintable():
                    instruction += event.unicode
        if snapshots and index < len(snapshots) - 1 and now - last >= 650:
            index, last = index + 1, now

        screen.fill(BG)
        _text(screen, title, "Custom map editor · V1R1 autonomous demo", (50, 35))
        _text(
            screen,
            small,
            "Click a tool, then click cells. One goal and one matching "
            "target are required.",
            (50, 78),
            MUTED,
        )
        pygame.draw.rect(screen, (38, 52, 70), input_box, border_radius=7)
        _text(screen, body, instruction, (65, 134))
        if active and (now // 500) % 2 == 0:
            cursor_x = 65 + body.size(instruction)[0] + 2
            pygame.draw.line(screen, TEXT, (cursor_x, 132), (cursor_x, 160), width=2)
        pygame.draw.rect(screen, ACCENT, start_button, border_radius=7)
        _text(screen, body, "START", (start_button.x + 43, 134), BG)
        pygame.draw.rect(screen, PANEL, replay, border_radius=7)
        _text(screen, body, "REPLAY", (replay.x + 32, 134))
        pygame.draw.rect(screen, PANEL, reset, border_radius=7)
        _text(screen, body, "RESET MAP", (reset.x + 23, 134))
        pygame.draw.rect(screen, PANEL, back, border_radius=7)
        _text(screen, small, "← BACK", (back.x + 23, back.y + 13))
        pygame.draw.rect(screen, PANEL, map_canvas, border_radius=12)
        if snapshots:
            # Reuse the shared renderer while fitting every custom map.
            pygame_demo.CELL = cell
            pygame_demo.GRID_ORIGIN = origin
            _draw_grid(screen, snapshots[index], small)
            _text(
                screen,
                body,
                f"Step {index + 1}/{len(snapshots)}: {snapshots[index].phase}",
                (map_canvas.x, map_canvas.bottom + 85),
                ACCENT,
            )
        else:
            for y in range(height):
                for x in range(width):
                    rect = pygame.Rect(
                        origin[0] + x * cell, origin[1] + y * cell, cell - 1, cell - 1
                    )
                    border = x in {0, width - 1} or y in {0, height - 1}
                    kind, item_color = cells.get(
                        (x, y), ("wall" if border else "empty", "grey")
                    )
                    fill = (92, 105, 122) if kind == "wall" else (42, 53, 70)
                    pygame.draw.rect(screen, fill, rect)
                    if kind in {"key", "ball"}:
                        _draw_icon(screen, rect, kind, COLORS[item_color])
                    elif kind == "door":
                        pygame.draw.rect(
                            screen,
                            COLORS.get(item_color, TEXT),
                            rect.inflate(-cell // 3, -4),
                        )
                    elif kind == "goal":
                        _draw_icon(screen, rect, "goal", (255, 209, 79))
                    if (x, y) == robot:
                        _draw_icon(screen, rect, "robot", (87, 188, 255), direction)
        pygame.draw.rect(screen, PANEL, sidebar, border_radius=10)
        _text(screen, body, "Tool", (sidebar.x + 30, sidebar.y + 20), ACCENT)
        for name, rect in tool_rects.items():
            pygame.draw.rect(
                screen, ACCENT if name == tool else (48, 63, 81), rect, border_radius=5
            )
            _text(
                screen,
                small,
                name.upper(),
                (rect.x + 12, rect.y + 12),
                BG if name == tool else TEXT,
            )
        _text(screen, body, "Color", (sidebar.centerx + 10, sidebar.y + 20), ACCENT)
        for name, rect in color_rects.items():
            pygame.draw.rect(
                screen,
                COLORS[name] if name == color else (48, 63, 81),
                rect,
                border_radius=5,
            )
            _text(
                screen,
                small,
                name.upper(),
                (rect.x + 12, rect.y + 12),
                BG if name == color else TEXT,
            )
        _text(
            screen,
            small,
            f"Width: {width}",
            (map_canvas.x + 62, map_canvas.bottom + 34),
        )
        _text(
            screen,
            small,
            f"Height: {height}",
            (map_canvas.x + 382, map_canvas.bottom + 34),
        )
        for name, rect in size_buttons.items():
            pygame.draw.rect(screen, PANEL, rect)
            _text(screen, small, name[-1], (rect.x + 16, rect.y + 9))
        _text(
            screen, small, "Robot heading", (sidebar.x + 30, direction_y - 35), ACCENT
        )
        for i, rect in enumerate(direction_buttons):
            pygame.draw.rect(screen, ACCENT if i == direction else (48, 63, 81), rect)
            arrow = ((1, 0), (0, 1), (-1, 0), (0, -1))[i]
            cx, cy = rect.center
            tip = (cx + arrow[0] * 15, cy + arrow[1] * 15)
            side = (-arrow[1] * 9, arrow[0] * 9)
            pygame.draw.polygon(
                screen,
                BG if i == direction else TEXT,
                [tip, (cx + side[0], cy + side[1]), (cx - side[0], cy - side[1])],
            )
        for rect, label in zip(
            examples,
            ("Example: go to the green ball", "Example: key → door → goal"),
            strict=True,
        ):
            pygame.draw.rect(screen, (48, 63, 81), rect)
            _text(screen, small, label, (rect.x + 10, rect.y + 11))
        pygame.draw.rect(screen, (42, 65, 82), code_button, border_radius=6)
        _text(
            screen,
            small,
            "</> MAP CODE: EDIT / IMPORT",
            (code_button.x + 14, code_button.y + 12),
            ACCENT,
        )
        _text(
            screen,
            small,
            status,
            (50, screen_height - 45),
            ERROR if "exactly" in status or "must" in status else TEXT,
        )
        if code_visible:
            pygame.draw.rect(screen, (10, 16, 26), modal, border_radius=12)
            pygame.draw.rect(screen, ACCENT, modal, width=2, border_radius=12)
            _text(
                screen, title, "Map code (JSON)", (modal.x + 28, modal.y + 22), ACCENT
            )
            _text(
                screen,
                small,
                "Click anywhere to place the cursor, edit directly, then Import Map.",
                (modal.x + 28, modal.y + 68),
                MUTED,
            )
            pygame.draw.rect(screen, (22, 32, 46), code_area, border_radius=6)
            if max_scroll:
                pygame.draw.rect(screen, (43, 58, 76), scroll_track, border_radius=4)
                pygame.draw.rect(screen, ACCENT, scroll_thumb, border_radius=4)
            lines = code_text.splitlines() or [""]
            visible_line_count = max(1, (code_area.height - 28) // 22)
            max_scroll = max(0, len(lines) - visible_line_count)
            code_scroll_line = min(code_scroll_line, max_scroll)
            selection = (
                None
                if code_anchor is None or code_anchor == code_cursor
                else sorted((code_anchor, code_cursor))
            )
            old_clip = screen.get_clip()
            screen.set_clip(code_area)
            line_start = sum(len(line) + 1 for line in lines[:code_scroll_line])
            for line_no, line in enumerate(
                lines[code_scroll_line : code_scroll_line + visible_line_count]
            ):
                line_end = line_start + len(line)
                if selection is not None:
                    selection_start = max(selection[0], line_start)
                    selection_end = min(selection[1], line_end)
                    if selection_start < selection_end:
                        prefix = line[: selection_start - line_start]
                        chosen = line[
                            selection_start - line_start : selection_end - line_start
                        ]
                        pygame.draw.rect(
                            screen,
                            (48, 96, 133),
                            pygame.Rect(
                                code_area.x + 16 + small.size(prefix)[0],
                                code_area.y + 13 + line_no * 22,
                                max(3, small.size(chosen)[0]),
                                21,
                            ),
                        )
                _text(
                    screen,
                    small,
                    line[:150],
                    (code_area.x + 16, code_area.y + 14 + line_no * 22),
                    TEXT,
                )
                line_start = line_end + 1
            before_cursor = code_text[:code_cursor]
            cursor_line = before_cursor.count("\n")
            cursor_column = before_cursor.rsplit("\n", 1)[-1]
            if (
                code_scroll_line <= cursor_line < code_scroll_line + visible_line_count
                and (now // 500) % 2 == 0
            ):
                cursor_x = code_area.x + 16 + small.size(cursor_column)[0]
                cursor_y = code_area.y + 14 + (cursor_line - code_scroll_line) * 22
                pygame.draw.line(
                    screen,
                    TEXT,
                    (cursor_x, cursor_y),
                    (cursor_x, cursor_y + 19),
                    width=2,
                )
            screen.set_clip(old_clip)
            pygame.draw.rect(screen, ACCENT, import_button, border_radius=6)
            _text(
                screen,
                small,
                "IMPORT MAP",
                (import_button.x + 38, import_button.y + 12),
                BG,
            )
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()
    return 0
