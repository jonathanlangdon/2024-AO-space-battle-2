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

            data = self.rfile.readline().decode() # reads until '\n' encountered
            json_data = json.loads(str(data))
            # uncomment the following line to see pretty-printed data
                # print(json.dumps(json_data, indent=4, sort_keys=True))
            if first_run:
                grid_y = json_data["game_info"]["map_height"]
                grid_x = json_data["game_info"]["map_width"]
                game_grid = {(x, y): None for x in range(grid_x) for y in range(grid_y)}
                first_run = False

            for tile in json_data["tile_updates"]:
                game_grid[(tile["x"], tile["y"])] = tile
                
            for unit in json_data["unit_updates"]:
                units[unit["id"]] = unit

            # Extract resources safely
            for (x, y), tile in game_grid.items():
                if tile is not None and "resources" in tile and tile["resources"] is not None:
                    resources[(x, y)] = tile["resources"]

            # Print resources in a readable format
            if resources:
                print("Resources on the map:")
                for location, resource in resources.items():
                    print(f"Location {location}: Resources {resource}")
            else:
                print("No resources found on the map.")
                
            response = game.get_random_move(json_data).encode()
            self.wfile.write(response)



class Game:
    def __init__(self):
        self.units = set() # set of unique unit ids
        self.directions = ['N', 'S', 'E', 'W']

    def get_random_move(self, json_data):
        
        units = set([unit['id'] for unit in json_data['unit_updates'] if unit['type'] != 'base'])
        self.units |= units # add any additional ids we encounter
        unit = random.choice(tuple(self.units))
        direction = random.choice(self.directions)
        move = 'MOVE'
        command = {"commands": [{"command": move, "unit": unit, "dir": direction}]}
        response = json.dumps(command, separators=(',',':')) + '\n'
        return response

if __name__ == "__main__":
    port = int(sys.argv[1]) if (len(sys.argv) > 1 and sys.argv[1]) else 9090
    host = '0.0.0.0'

    server = ss.TCPServer((host, port), NetworkHandler)
    print("listening on {}:{}".format(host, port))
    server.serve_forever()
