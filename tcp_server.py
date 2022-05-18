import socket
import socketserver
import threading
import os


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")


from settings import TCP_HOST, TCP_PORT

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request.recv(1024)
        print("{} wrote:".format(self.client_address[0]))
        print('TCP SERVER GET: ', data)
        TCPBrokerConnections.connect_user(self, data)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


if __name__ == "__main__":
    import django
    django.setup()
    from tcp_server.tcp_broker import TCPBrokerConnections
    from tcp_server.helpers.game_storage_helper import GameStorageHelper
    server = ThreadedTCPServer((TCP_HOST, TCP_PORT), ThreadedTCPRequestHandler)
    with server:
        GameStorageHelper.clear()
        ip, port = server.server_address
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.start()
        print("Server loop running in thread:", server_thread.name)
        print(f'IP: {ip}; port: {port}')
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()
        server.server_close()
        print('\nThreadedTCPServer close')

