#!/usr/bin/python

import sys
import json
import random

if (sys.version_info > (3, 0)):
    print("Python 3.X detected")
    import socketserver as ss
else:
    print("Python 2.X detected")
    import SocketServer as ss


class NetworkHandler(ss.StreamRequestHandler):
    def handle(self):
        game = Game()
        first_run = True

        game_grid = {}
        units = {}
        resources = {}

        while True:
            data = self.rfile.readline().decode()  # reads until '\n' encountered
            if not data:
                break  # Handle client disconnect
            json_data = json.loads(str(data))

            if first_run:
                grid_y = json_data["game_info"]["map_height"]
                grid_x = json_data["game_info"]["map_width"]
                game_grid = {(x, y): None for x in range(grid_x) for y in range(grid_y)}
                first_run = False

            for tile in json_data["tile_updates"]:
                x, y = tile["x"], tile["y"]
                game_grid[(x, y)] = tile

                # Update resources dictionary
                if tile.get("resources"):
                    resources[(x, y)] = tile["resources"]
                else:
                    # Remove resource if it's depleted
                    resources.pop((x, y), None)

            for unit in json_data["unit_updates"]:
                units[unit["id"]] = unit

            # Update the Game instance with the latest grid, units, and resources
            game.game_grid = game_grid
            game.units = units
            game.resources = resources

            # Generate and send commands
            response = game.get_unit_commands(json_data).encode()
            self.wfile.write(response)


class Game:
    def __init__(self):
        self.units = {}          # unit_id to unit data
        self.game_grid = {}      # (x, y) to tile data
        self.resources = {}      # (x, y) to resource amount
        self.directions = ['N', 'E', 'S', 'W']
        self.unit_states = {}    # unit_id to state data

    def get_unit_commands(self, json_data):
        commands = {"commands": []}

        build_command = {"command": "CREATE", "type": "worker"}
        commands["commands"].append(build_command)

        base_pos = self.find_base_position()  # Get base position for workers to return to

        for unit_id, unit in self.units.items():
            if unit_id not in self.unit_states:
                # Initialize unit state
                self.unit_states[unit_id] = {
                    'current_direction': random.choice(self.directions),
                    'wall_hugging': False,
                    'wall_side': 'right'  # or 'left', depending on preference
                }
            unit_state = self.unit_states[unit_id]

            if unit['type'] == 'worker':
                unit_pos = (unit['x'], unit['y'])
                resources_collected = unit.get('resource', 0)
                print(f"Worker {unit_id} at {unit_pos} has {resources_collected} resources collected")

                if resources_collected >= 10:
                    # Move toward base and deposit
                    if base_pos and self.is_adjacent(unit_pos, base_pos):
                        # Adjacent to base, issue DEPOSIT command
                        command = {"command": "DEPOSIT", "unit": unit_id}
                        print(f"Deposit command for unit {unit_id} at base")
                        commands["commands"].append(command)
                    elif base_pos:
                        # Move toward base
                        direction = self.get_direction_toward(unit_pos, base_pos)
                        direction = self.get_navigable_direction(unit_pos, direction, unit_state)
                        if direction:
                            command = {"command": "MOVE", "unit": unit_id, "dir": direction}
                            print(f"Returning to base for unit {unit_id} towards {direction}")
                            commands["commands"].append(command)
                    else:
                        # No base found, move randomly
                        direction = self.get_random_direction(unit_pos, unit_state)
                        if direction:
                            command = {"command": "MOVE", "unit": unit_id, "dir": direction}
                            print(f"Random move for unit {unit_id} towards {direction}")
                            commands["commands"].append(command)
                else:
                    # Gathering resources
                    closest_resource_pos = self.find_closest_resource(unit_pos)
                    if closest_resource_pos and self.is_adjacent(unit_pos, closest_resource_pos):
                        # Adjacent to resource, issue GATHER command with direction
                        direction = self.get_direction_toward(unit_pos, closest_resource_pos)
                        command = {"command": "GATHER", "unit": unit_id, "dir": direction}
                        print(f"Gather command for unit {unit_id} at {unit_pos} towards {direction}")
                        commands["commands"].append(command)
                    elif closest_resource_pos:
                        # Move toward resource
                        direction = self.get_direction_toward(unit_pos, closest_resource_pos)
                        direction = self.get_navigable_direction(unit_pos, direction, unit_state)
                        if direction:
                            command = {"command": "MOVE", "unit": unit_id, "dir": direction}
                            print(f"Moving to resource for unit {unit_id} towards {direction}")
                            commands["commands"].append(command)
                    else:
                        # Move randomly
                        direction = self.get_random_direction(unit_pos, unit_state)
                        if direction:
                            command = {"command": "MOVE", "unit": unit_id, "dir": direction}
                            print(f"Random move for unit {unit_id} towards {direction}")
                            commands["commands"].append(command)

        response = json.dumps(commands, separators=(',', ':')) + '\n'
        print("Commands to send:", commands)
        return response

    def find_base_position(self):
        for unit in self.units.values():
            if unit['type'] == 'base':
                return (unit['x'], unit['y'])
        return None

    def find_closest_resource(self, unit_pos):
        min_distance = float('inf')
        closest_resource_pos = None
        for resource_pos in self.resources.keys():
            distance = self.manhattan_distance(unit_pos, resource_pos)
            if distance < min_distance:
                min_distance = distance
                closest_resource_pos = resource_pos
        return closest_resource_pos

    def is_adjacent(self, pos1, pos2):
        dx = abs(pos1[0] - pos2[0])
        dy = abs(pos1[1] - pos2[1])
        return (dx == 1 and dy == 0) or (dx == 0 and dy == 1)

    def manhattan_distance(self, pos1, pos2):
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def get_direction_toward(self, unit_pos, target_pos):
        dx = target_pos[0] - unit_pos[0]
        dy = target_pos[1] - unit_pos[1]
        if dx == 1 and dy == 0:
            return 'E'
        elif dx == -1 and dy == 0:
            return 'W'
        elif dx == 0 and dy == 1:
            return 'S'
        elif dx == 0 and dy == -1:
            return 'N'
        else:
            # For non-adjacent positions, choose primary direction
            if abs(dx) > abs(dy):
                return 'E' if dx > 0 else 'W'
            elif dy != 0:
                return 'S' if dy > 0 else 'N'
            else:
                return None  # Already at the target position

    def get_navigable_direction(self, unit_pos, direction, unit_state):
        next_pos = self.get_next_position(unit_pos, direction)
        if self.is_tile_blocked(next_pos):
            # Start wall-hugging if not already
            if not unit_state.get('wall_hugging'):
                unit_state['wall_hugging'] = True
                unit_state['wall_side'] = 'right'  # or 'left'
                unit_state['current_direction'] = direction
            # Wall-hugging behavior
            wall_hug_direction = self.wall_hugging_direction(unit_pos, unit_state)
            return wall_hug_direction
        else:
            # If the path is clear, stop wall-hugging
            unit_state['wall_hugging'] = False
            return direction

    def wall_hugging_direction(self, unit_pos, unit_state):
        # Determine the sequence of directions to check based on wall side
        if unit_state['wall_side'] == 'right':
            directions_order = self.get_right_hand_rule_directions(unit_state['current_direction'])
        else:
            directions_order = self.get_left_hand_rule_directions(unit_state['current_direction'])

        # Try directions in the determined order
        for dir in directions_order:
            next_pos = self.get_next_position(unit_pos, dir)
            if not self.is_tile_blocked(next_pos):
                unit_state['current_direction'] = dir
                return dir
        # All directions are blocked; stay in place
        return None

    def get_right_hand_rule_directions(self, current_direction):
        # Returns directions in order based on the right-hand rule
        
        order = {
            'N': ['E', 'N', 'W', 'S'],
            'E': ['S', 'E', 'N', 'W'],
            'S': ['W', 'S', 'E', 'N'],
            'W': ['N', 'W', 'S', 'E']
        }
        return order[current_direction]

    def get_left_hand_rule_directions(self, current_direction):
        # Returns directions in order based on the left-hand rule
        
        order = {
            'N': ['W', 'N', 'E', 'S'],
            'E': ['N', 'E', 'S', 'W'],
            'S': ['E', 'S', 'W', 'N'],
            'W': ['S', 'W', 'N', 'E']
        }
        return order[current_direction]

    def get_random_direction(self, unit_pos, unit_state):
        direction = unit_state['current_direction']
        next_pos = self.get_next_position(unit_pos, direction)
        if self.is_tile_blocked(next_pos):
            # Hit an obstacle, pick a new random direction
            alternative_directions = self.directions.copy()
            alternative_directions.remove(direction)
            random.shuffle(alternative_directions)
            for alt_direction in alternative_directions:
                next_pos = self.get_next_position(unit_pos, alt_direction)
                if not self.is_tile_blocked(next_pos):
                    unit_state['current_direction'] = alt_direction
                    return alt_direction
            return None
        else:
            return direction

    def get_next_position(self, unit_pos, direction):
        x, y = unit_pos
        if direction == 'N':
            return (x, y - 1)
        elif direction == 'S':
            return (x, y + 1)
        elif direction == 'E':
            return (x + 1, y)
        elif direction == 'W':
            return (x - 1, y)

    def is_tile_blocked(self, pos):
        tile = self.game_grid.get(pos)
        if tile is None:
            # We may be off the map
            return True
        return tile.get('blocked', False)


if __name__ == "__main__":
    port = int(sys.argv[1]) if (len(sys.argv) > 1 and sys.argv[1]) else 9090
    host = '0.0.0.0'

    server = ss.TCPServer((host, port), NetworkHandler)
    print("listening on {}:{}".format(host, port))
    server.serve_forever()
