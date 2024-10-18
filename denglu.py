from PyQt5.QtCore import QThread, pyqtSignal
import paramiko
from paramiko import ssh_exception
import warnings
from PyQt5.QtCore import Qt, QTimer


from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QWidget,QTextEdit, QApplication, QDialog



warnings.filterwarnings("ignore", category=DeprecationWarning)

class CommandThread(QThread):
    commandResult = pyqtSignal(str)  # 自定义信号，用于发送命令的输出

    def __init__(self, ssh_client, ssh_command, isblocking=False):
        super(CommandThread, self).__init__()
        self.ssh_client = ssh_client
        self.ssh_command = ssh_command
        self.isblocking = isblocking

    def run(self):
        if self.isblocking is True:
            try:
                ssh_stdin, ssh_stdout, ssh_stderr = self.ssh_client.exec_command(self.ssh_command)
                while True:
                    line = ssh_stdout.readline()
                    if not line:
                        break
                    self.commandResult.emit(line.strip('\n'))
                while True:
                    errline = ssh_stderr.readline()
                    if not errline:
                        break
                    self.commandResult.emit('ERR-------'+errline.strip('\n'))
            except paramiko.ssh_exception.SSHException as e:
                self.commandResult.emit(f"Error executing command: {e}")
        else:
            try:
                ssh_stdin, ssh_stdout, ssh_stderr = self.ssh_client.exec_command(self.ssh_command)
                print(type(ssh_stdout))
                stdout = ssh_stdout.read().decode()
                stderr = ssh_stderr.read().decode()
                # 合并stdout和stderr
                combined_output = stdout + "\n" + stderr if stderr else stdout
                self.commandResult.emit(combined_output)
            except Exception as e:
                self.commandResult.emit(str(e))



class Pyssh(QThread):
    connectionResult = pyqtSignal(bool, str)  # 自定义connectionResult信号

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
            self.connectionResult.emit(True, "SSH Connection Successful")
        except ssh_exception.SSHException as e:
            self.connectionResult.emit(False, f"SSH Connection Error: {e}")


    def close_ssh_connection(self):
        if self.ssh_client:
            self.ssh_client.close()
            print("SSH connection closed.")
        if self.transport:
            self.transport.close()
        self.quit()


class NewWindow(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.init_UI()



    def init_UI(self):
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint)
        # self.setWindowFlags(self.windowFlags() | Qt.Dialog)
        self.setGeometry(300, 300, 800, 600)
        self.setWindowTitle(self.title)
        layout = QVBoxLayout()
        self.sys_text = QTextEdit(self)
        self.sys_text.setReadOnly(True)
        layout.addWidget(self.sys_text)
        self.setLayout(layout)

    def append_text(self, text):
        self.sys_text.append(text)

    def update_text(self, text):
        self.sys_text.setPlainText(text)


class Login_window(QWidget):
    def __init__(self):
        super().__init__()
        self.set_centralWindow()
        self.windows = {}


    def onButtonClick(self):
        host = '192.168.0.35'
        port = 22
        ssh_user = 'patrol'
        ssh_passwd = 'cbs_chiebot1003'

        self.ssh_executor = Pyssh(host, port, ssh_user, ssh_passwd)

        self.ssh_executor.connectionResult.connect(lambda success, message: print(message) if success else print("Connection failed:", message))

        self.ssh_executor.start()


    def onCommandClick3(self):
        btn_name = self.sender().text()
        if self.windows.get(btn_name):
            self.windows[btn_name].show()
            self.windows[btn_name].activateWindow()
        else:
            new_win = NewWindow(btn_name, self)
            new_win.show()
            # ssh_command = 'sudo systemctl restart docker && echo -e "------" && sudo systemctl status docker'
            # ssh_command = 'docker ps -a'
            ssh_command = 'docker logs  --tail 100 {containername}'.format(containername=btn_name)

            self.command_thread = CommandThread(self.ssh_executor.ssh_client, ssh_command, isblocking=False)
            self.command_thread.commandResult.connect(new_win.append_text)
            self.command_thread.start()
            self.windows[btn_name] = new_win
            print(self.windows)


    def set_centralWindow(self):
        self.setGeometry(1000, 500, 800, 600)
        screen = QApplication.desktop().screenGeometry()
        window_size = self.geometry()
        x = (screen.width() - window_size.width()) // 2
        y = (screen.height() - window_size.height()) // 2
        self.move(x, y)
        self.setWindowTitle('新建连接')
        layout = QVBoxLayout(self)
        self.con_btn = QPushButton("点击连接")
        self.con_btn.clicked.connect(self.onButtonClick)
        self.con_btn2 = QPushButton("patrol-auth")
        self.con_btn2.clicked.connect(self.onCommandClick3)
        self.con_btn3 = QPushButton("patrol-mysql")
        self.con_btn3.clicked.connect(self.onCommandClick3)

        layout.addWidget(self.con_btn)
        layout.addWidget(self.con_btn2)
        layout.addWidget(self.con_btn3)
        layout.addStretch()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    lw = Login_window()
    lw.show()
    sys.exit(app.exec_())
