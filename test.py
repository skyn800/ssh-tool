import paramiko
from PyQt5.QtWidgets import QWidget, QPushButton, QProgressBar, QVBoxLayout, QApplication
from PyQt5.QtCore import QBasicTimer, pyqtSlot, QThread, pyqtSignal


class FileTransferThread(QThread):
    # 定义信号，用于发送进度更新
    progressUpdated = pyqtSignal(int, int)

    def __init__(self, ssh_ip, ssh_user, ssh_password, ssh_port, local_path, remote_path, file_type):
        super(FileTransferThread, self).__init__()
        self.ssh_ip = ssh_ip
        self.ssh_user = ssh_user
        self.ssh_password = ssh_password
        self.ssh_port = ssh_port
        self.local_path = local_path
        self.remote_path = remote_path
        self.file_type = file_type  # 'upload' 或 'download'

    def run(self):
        self.connect()
        if self.file_type == 'upload':
            self.upload_file()
        elif self.file_type == 'download':
            self.download_file()
        self.close()

    def connect(self):
        self.transport = paramiko.Transport((self.ssh_ip, self.ssh_port))
        self.transport.connect(username=self.ssh_user, password=self.ssh_password)
        self.sftp = paramiko.SFTPClient.from_transport(self.transport)

    def download_file(self):
        with open(self.local_path, 'wb') as f:
            def callback(transferred, total):
                self.progressUpdated.emit(transferred, total)
            self.sftp.getfo(self.remote_path, f, callback=callback)

    def upload_file(self):
        with open(self.local_path, 'rb') as f:
            def callback(transferred, total):
                self.progressUpdated.emit(transferred, total)
            self.sftp.putfo(f, self.remote_path, callback=callback)

    def close(self):
        if self.sftp:
            self.sftp.close()
        if self.transport:
            self.transport.close()

# 使用示例
class MyClass(QWidget):
    # ...
    def start_file_transfer(self):
        self.file_exec_thread = FileTransferThread("192.168.0.35", "patrol", "cbs_chiebot1003", 22, "main.zip", "/tmp/main.zip", 'upload')
        self.file_exec_thread.progressUpdated.connect(self.update_progress)
        self.file_exec_thread.start()

    # ...