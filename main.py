import socket
import threading
import select

# Автоопределение локального IP компьютера в Wi-Fi сети
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '0.0.0.0'
    finally:
        s.close()
    return ip

def handle_client(client_socket, client_address):
    device_ip = client_address[0]
    try:
        # 1. Авторизация SOCKS5
        client_socket.recv(1)  # Версия (\x05)
        nmethods = ord(client_socket.recv(1))
        client_socket.recv(nmethods)  # Список методов
        client_socket.sendall(b'\x05\x00')  # Без пароля

        # 2. Получение запроса от телефона
        client_socket.recv(1)  # Версия (\x05)
        cmd = client_socket.recv(1)  # Команда (\x01 - CONNECT)
        client_socket.recv(1)  # Резерв (\x00)
        address_type = client_socket.recv(1)

        # Определение целевого адреса
        if address_type == b'\x01':    # IPv4
            address = socket.inet_ntoa(client_socket.recv(4))
        elif address_type == b'\x03':  # Доменное имя (Важно для YouTube!)
            domain_length = ord(client_socket.recv(1))
            address = client_socket.recv(domain_length).decode()
        else:
            return

        port = int.from_bytes(client_socket.recv(2), 'big')

        # Логгируем попытку подключения устройства
        print(f"[➔] Устройство [{device_ip}] запрашивает: {address}:{port}")

        # 3. Подключение к сайту от лица ПК (Здесь трафик перехватывает Zapret!)
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_socket.settimeout(10)
        try:
            remote_socket.connect((address, port))
        except Exception as err:
            print(f"[🗙] Ошибка подключения для [{device_ip}] к {address}: {err}")
            return

        # Успешный ответ телефону
        client_socket.sendall(b'\x05\x00\x00\x01' + socket.inet_aton('0.0.0.0') + (0).to_bytes(2, 'big'))
        print(f"[✓] Успешный туннель для [{device_ip}] -> {address}")

        # 4. Пересылка пакетов в обе стороны
        sockets = [client_socket, remote_socket]
        while True:
            readable, _, _ = select.select(sockets, [], [], 60)
            if not readable:
                break  # Таймаут неактивности

            if client_socket in readable:
                data = client_socket.recv(8192)
                if not data: break
                remote_socket.sendall(data)
                
            if remote_socket in readable:
                data = remote_socket.recv(8192)
                if not data: break
                client_socket.sendall(data)
                
    except Exception:
        pass
    finally:
        client_socket.close()

def start_socks_server():
    ip = get_local_ip()
    port = 1080
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', port))
    server.listen(200)
    
    print("="*60)
    print(f"[ СЕРВЕР ЗАПУЩЕН ]")
    print(f"-> IP компьютера в сети: {ip}")
    print(f"-> Порт сервера: {port}")
    print(f"-> Ожидание подключений от телефона...")
    print("="*60)
    
    while True:
        try:
            client_sock, client_addr = server.accept()
            # Передаем адрес устройства в поток логирования
            threading.Thread(target=handle_client, args=(client_sock, client_addr), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[-] Сервер остановлен пользователем.")
            break

if __name__ == '__main__':
    start_socks_server()
