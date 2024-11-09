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
        self.units = {}  # unit_id to unit data
        self.game_grid = {}
        self.resources = {}
        self.directions = ['N', 'S', 'E', 'W']
        self.unit_states = {}  # Dictionary to track per-unit states

    def get_unit_commands(self, json_data):
        commands = {"commands": []}
        base_pos = self.find_base_position()  # Get base position for workers to return to

        for unit_id, unit in self.units.items():
            if unit_id not in self.unit_states:
                # Initialize unit state
                self.unit_states[unit_id] = {'current_direction': random.choice(self.directions)}
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
                        direction = self.get_navigable_direction(unit_pos, direction)
                        if direction:
                            command = {"command": "MOVE", "unit": unit_id, "dir": direction}
                            print(f"Return to base for unit {unit_id} towards {direction}")
                            commands["commands"].append(command)
                    else:
                        # No base found, move randomly
                        direction = unit_state['current_direction']
                        direction = self.get_navigable_random_direction(unit_pos, direction, unit_state)
                        if direction:
                            command = {"command": "MOVE", "unit": unit_id, "dir": direction}
                            print(f"Random move for unit {unit_id} towards {direction}")
                            commands["commands"].append(command)
                else:
                    # Gathering resources
                    closest_resource_pos = self.find_closest_resource(unit_pos)
                    if closest_resource_pos and self.is_adjacent(unit_pos, closest_resource_pos):
                        # Adjacent to resource, directly issue GATHER command without modifying direction
                        direction = self.get_direction_toward(unit_pos, closest_resource_pos)
                        command = {"command": "GATHER", "unit": unit_id, "dir": direction}
                        print(f"Gather command for unit {unit_id} at {unit_pos}")
                        commands["commands"].append(command)
                    elif closest_resource_pos:
                        # Move toward resource
                        direction = self.get_direction_toward(unit_pos, closest_resource_pos)
                        direction = self.get_navigable_direction(unit_pos, direction)
                        if direction:
                            command = {"command": "MOVE", "unit": unit_id, "dir": direction}
                            print(f"Move command for unit {unit_id} towards {direction}")
                            commands["commands"].append(command)
                    else:
                        # Move randomly
                        direction = unit_state['current_direction']
                        direction = self.get_navigable_random_direction(unit_pos, direction, unit_state)
                        if direction:
                            command = {"command": "MOVE", "unit": unit_id, "dir": direction}
                            print(f"Random move for unit {unit_id} towards {direction}")
                            commands["commands"].append(command)

        if not commands["commands"]:
            print("No commands to send.")  # Debug if no commands are created
        else:
            print("Commands to send:", commands)  # Debug successful commands

        response = json.dumps(commands, separators=(',', ':')) + '\n'
        return response

    def find_base_position(self):
        """Find the position of the base on the grid."""
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
        """Check if two positions are adjacent on the grid."""
        dx = abs(pos1[0] - pos2[0])
        dy = abs(pos1[1] - pos2[1])
        return (dx == 1 and dy == 0) or (dx == 0 and dy == 1)

    def manhattan_distance(self, pos1, pos2):
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def get_direction_toward(self, unit_pos, target_pos):
        dx = target_pos[0] - unit_pos[0]
        dy = target_pos[1] - unit_pos[1]
        if abs(dx) > abs(dy):
            # Move in x direction
            if dx > 0:
                return 'E'
            elif dx < 0:
                return 'W'
        elif dy != 0:
            # Move in y direction
            if dy > 0:
                return 'S'
            elif dy < 0:
                return 'N'
        else:
            return None  # Already at the target position

    def get_navigable_direction(self, unit_pos, direction):
        # Check if the tile in the given direction is blocked
        next_pos = self.get_next_position(unit_pos, direction)
        if self.is_tile_blocked(next_pos):
            # Tile is blocked, need to find alternative
            alternative_directions = self.get_alternative_directions(direction)
            for alt_direction in alternative_directions:
                next_pos = self.get_next_position(unit_pos, alt_direction)
                if not self.is_tile_blocked(next_pos):
                    return alt_direction
            # All adjacent tiles are blocked, stay in place
            return None
        else:
            # Tile is not blocked, proceed in the original direction
            return direction

    def get_navigable_random_direction(self, unit_pos, direction, unit_state):
        # Continue in current direction if possible
        next_pos = self.get_next_position(unit_pos, direction)
        if self.is_tile_blocked(next_pos):
            # Hit an obstacle, pick a new random direction
            alternative_directions = list(self.directions)
            alternative_directions.remove(direction)
            random.shuffle(alternative_directions)
            for alt_direction in alternative_directions:
                next_pos = self.get_next_position(unit_pos, alt_direction)
                if not self.is_tile_blocked(next_pos):
                    unit_state['current_direction'] = alt_direction
                    return alt_direction
            # No available direction, stay in place
            return None
        else:
            # Continue in current direction
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

    def get_alternative_directions(self, direction):
        # Define left and right of the current direction
        if direction == 'N':
            return ['E', 'W', 'S']
        elif direction == 'S':
            return ['E', 'W', 'N']
        elif direction == 'E':
            return ['N', 'S', 'W']
        elif direction == 'W':

            return ['N', 'S', 'E']


if __name__ == "__main__":
    port = int(sys.argv[1]) if (len(sys.argv) > 1 and sys.argv[1]) else 9090
    host = '0.0.0.0'

    server = ss.TCPServer((host, port), NetworkHandler)
    print("listening on {}:{}".format(host, port))
    server.serve_forever()
