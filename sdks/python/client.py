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
            json_data = json.loads(str(data))

            if first_run:
                grid_y = json_data["game_info"]["map_height"]
                grid_x = json_data["game_info"]["map_width"]
                game_grid = {(x, y): None for x in range(grid_x) for y in range(grid_y)}
                first_run = False

            for tile in json_data["tile_updates"]:
                game_grid[(tile["x"], tile["y"])] = tile

            for unit in json_data["unit_updates"]:
                units[unit["id"]] = unit

            # Extract resources safely and debug
            for (x, y), tile in game_grid.items():
                if tile is not None and tile.get("resources") is not None:
                    resources[(x, y)] = tile["resources"]

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

    def get_unit_commands(self, json_data):
        commands = {"commands": []}
        for unit_id, unit in self.units.items():
            if unit['type'] == 'worker':
                unit_pos = (unit['x'], unit['y'])
                closest_resource_pos = self.find_closest_resource(unit_pos)
                if closest_resource_pos:
                    # Move toward the closest resource
                    direction = self.get_direction_toward(unit_pos, closest_resource_pos)
                else:
                    # Move randomly if no resources are found
                    direction = random.choice(self.directions)

                if direction:
                    command = {"command": "MOVE", "unit": unit_id, "dir": direction}
                    commands["commands"].append(command)
                    print(f"Command for unit {unit_id}: {command}")  # Debug each command

        if not commands["commands"]:
            print("No commands to send.")  # Debug if no commands are created
        else:
            print("Commands to send:", commands)  # Debug successful commands

        response = json.dumps(commands, separators=(',', ':')) + '\n'
        return response

    def find_closest_resource(self, unit_pos):
        min_distance = float('inf')
        closest_resource_pos = None
        for resource_pos in self.resources.keys():
            distance = self.manhattan_distance(unit_pos, resource_pos)
            if distance < min_distance:
                min_distance = distance
                closest_resource_pos = resource_pos
        return closest_resource_pos

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


if __name__ == "__main__":
    port = int(sys.argv[1]) if (len(sys.argv) > 1 and sys.argv[1]) else 9090
    host = '0.0.0.0'

    server = ss.TCPServer((host, port), NetworkHandler)
    print("listening on {}:{}".format(host, port))
    server.serve_forever()
