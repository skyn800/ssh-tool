from PyQt5.QtCore import QThread, pyqtSignal
import paramiko
from paramiko import ssh_exception



class FileExec():
    def __init__(self, ssh_ip, ssh_user, ssh_password, ssh_port):
        self.ssh_ip = ssh_ip
        self.ssh_user = ssh_user
        self.ssh_port = int(ssh_port)
        self.ssh_password = ssh_password

    def connect(self):
        # 创建SSH传输通道
        self.transport = paramiko.Transport((self.ssh_ip, self.ssh_port))
        self.transport.connect(username=self.ssh_user, password=self.ssh_password)
        # 创建SFTP客户端
        self.sftp = paramiko.SFTPClient.from_transport(self.transport)

    def download_file(self, remote_path, local_path, progress_callback):
        with open(local_path, 'wb', buffering=2048*2048) as f:
            self.sftp.getfo(remote_path, f, callback=lambda transferred, total: progress_callback(transferred, total))

    def upload_file(self, local_path, remote_path, progress_callback):
        with open(local_path, 'rb', buffering=2048*2048) as f:
            self.sftp.putfo(f, remote_path, callback=lambda transferred, total: progress_callback(transferred, total))

    def close(self):
        if self.sftp:
            self.sftp.close()
        if self.transport:
            self.transport.close()



# 突出了INFO,ERROR,WARN颜色变化
class CommandThread(QThread):
    commandResult = pyqtSignal(str)  # 自定义信号，用于发送命令的输出

    def __init__(self, ssh_client, ssh_command):
        super(CommandThread, self).__init__()
        self.ssh_client = ssh_client
        self.ssh_command = ssh_command

    def run(self):
        try:
            ssh_stdin, ssh_stdout, ssh_stderr = self.ssh_client.exec_command(self.ssh_command)
            while True:
                line = ssh_stdout.readline()
                if not line:
                    break
                formatted_line = self.format_line(line)
                self.commandResult.emit(formatted_line)
            while True:
                errline = ssh_stderr.readline()
                if not errline:
                    break
                self.commandResult.emit('<span style="color: red;">ERR-------' + errline.strip('\n') + '</span>')
        except paramiko.ssh_exception.SSHException as e:
            self.commandResult.emit(f"Error executing command: {e}")

    def format_line(self, line):
        if 'INFO' in line:
            line = line.replace('INFO', '<span style="color: #008000;">INFO</span>')
        elif 'WARN' in line:
            line = line.replace('WARN', '<span style="color: #0087FF;">WARN</span>')
        elif 'ERROR' in line:
            line = line.replace('ERROR', '<span style="color: #FF0000;">ERROR</span>')
        return line

# 纯文本输出
# class CommandThread(QThread):
#     commandResult = pyqtSignal(str)  # 自定义信号，用于发送命令的输出
#
#     def __init__(self, ssh_client, ssh_command):
#         super(CommandThread, self).__init__()
#         self.ssh_client = ssh_client
#         self.ssh_command = ssh_command
#
#     def run(self):
#         try:
#             ssh_stdin, ssh_stdout, ssh_stderr = self.ssh_client.exec_command(self.ssh_command)
#             while True:
#                 line = ssh_stdout.readline()
#                 if not line:
#                     break
#                 self.commandResult.emit(line.strip('\n'))
#             while True:
#                 errline = ssh_stderr.readline()
#                 if not errline:
#                     break
#                 self.commandResult.emit('ERR-------'+errline.strip('\n'))
#         except paramiko.ssh_exception.SSHException as e:
#             self.commandResult.emit(f"Error executing command: {e}")


class Pyssh(QThread):
    connectionResult = pyqtSignal(bool, str)  # 自定义connectionResult信号，发给槽函数时带2个参数，参数类型bool和str

    def __init__(self, host, port, ssh_user, ssh_passwd):
        super(Pyssh, self).__init__()
        self.host = host
        self.port = int(port)
        self.ssh_user = ssh_user
        self.ssh_passwd = ssh_passwd
        self.transport = None
        self.ssh_client = None

    def run(self):
        try:
            self.transport = paramiko.Transport((self.host, self.port))
            self.transport.connect(username=self.ssh_user, password=self.ssh_passwd)
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client._transport = self.transport
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.connectionResult.emit(True, "SSH Connection Successful")  # emit(i)函数触发自定义信号将参数i发送给槽函数，槽函数接受信号，执行指定操作
        except ssh_exception.SSHException as e:
            self.connectionResult.emit(False, f"SSH Connection Error: {e}")

    def execute_ssh_command(self, ssh_command):
        if self.ssh_client and self.transport.is_active():
            try:
                ssh_stdin, ssh_stdout, ssh_stderr = self.ssh_client.exec_command(ssh_command)
                return ssh_stdout, ssh_stderr
            except ssh_exception.SSHException as e:
                print(f"Error executing command: {e}")
        else:
            print("SSH connection not established.")

    def close_ssh_connection(self):
        if self.ssh_client:
            self.ssh_client.close()
            print("SSH connection closed.")
        if self.transport:
            self.transport.close()
        self.quit()



if __name__ == "__main__":
    host = '192.168.0.35'
    port = 22
    ssh_user = 'patrol'
    ssh_passwd = 'cbs_chiebot1003'

    ssh_executor = Pyssh(host, port, ssh_user, ssh_passwd)

    ssh_executor.connectionResult.connect(
        lambda success, message: print(message) if success else print("Connection failed:", message))

    ssh_executor.start()
    # ssh_command = 'sudo systemctl restart docker && echo -e "------" && sudo systemctl status docker'
    # ssh_command = 'docker ps -a'
    ssh_command = 'docker logs -f --tail 100 upms'

    command_thread = CommandThread(ssh_executor.ssh_client, ssh_command)
    command_thread.commandResult.connect(lambda text: print(text))
    command_thread.start()
