import json
import os
import sys
import warnings
import datetime
from appLog import Logger

from PyQt5.QtGui import QIcon, QTextCursor, QImageReader, QTextBlockFormat, QCursor
from PyQt5.QtCore import Qt, pyqtSlot, QTimer
from PyQt5.QtWidgets import QPushButton, QLineEdit, QWidget, QVBoxLayout, QApplication, QFormLayout, \
    QTextEdit, QMessageBox, QMainWindow, QAction, QTabWidget, QHBoxLayout, QLabel, QFileDialog, QDialog, \
    QProgressBar, QComboBox, QGroupBox, QGridLayout, QScrollArea, QRadioButton
from Pyssh import Pyssh, CommandThread, FileExec
from https_sendRequests import HttpsRequest, HttpsPostRequest, signal_bus
from ModalDialog import ModalDialog, PointModalDialog
from commonfunc import CommonFunc
from TableWidget import DataTableWindow


warnings.filterwarnings("ignore", category=DeprecationWarning)

log = Logger('app.log', level='debug')
comfunc = CommonFunc()


class NewWindow(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.init_UI()

    def init_UI(self):
        """
        设置窗口控件
        @return:
        """
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint)
        self.setGeometry(300, 300, 800, 600)
        # self.showMaximized()
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


class Deploy_window(QMainWindow):
    def __init__(self, validation_window, sys_type, ssh_ip, ssh_user, ssh_thread, file_exec_instance):
        """
        @param validation_window: Login_window的实例
        @param ssh_ip:
        @param ssh_user:
        @param ssh_thread: 登录成功后创建的ssh实例
        """
        super().__init__()
        self.validation_window = validation_window
        self.login_type = sys_type
        self.login_ip = ssh_ip
        self.login_user = ssh_user
        self.ssh_instance = ssh_thread
        self.file_exec_instance = file_exec_instance
        self.initUI()

    def check_is_puresys(self):
        """
        检查系统是否符合纯净系统要求
        @return:
        """
        com_response, err_response, code_response = self.ssh_instance.execute_ssh_command('rpm -qa|grep docker-ce')
        log.logger.info('检测纯净系统命令返回码{status_code}'.format(status_code=code_response))
        if code_response == 0:
            QMessageBox.critical(self, '禁止登录',
                                 '检测到{host}已部署系统,禁止操作！请切换patrol或robot登录调试'.format(
                                     host=self.login_ip))
            return False
        else:
            return True

    def check_user_exit(self):
        """
        检查patrol或robot是否创建成功
        :return: 成功True，失败False
        """
        com_response, err_response, code_response = self.ssh_instance.execute_ssh_command('id -u patrol || id -u robot')
        if code_response == 0:
            return True
        else:
            QMessageBox.critical(self, 'User Error',
                                 '检测到{shfile}执行结果异常，联系研发查看'.format(shfile='createuser.sh'))
            return False

    def handle_thread_finished(self):
        """
        线程结束时操作
        :return:
        """
        text = self.zip_text.toPlainText()
        with open('logs/output.log', 'a', encoding='UTF-8') as file:
            file.write(text)

    def handle_createuser_shfile(self):
        """
        处理createuser.sh逻辑
        @return:
        """
        get_filename_path, _ = QFileDialog.getOpenFileName(self, caption="选择文件", directory=self.desktop_path,
                                                           filter="Shell脚本文件 (*.sh)")
        filename = os.path.basename(get_filename_path)  # createuser.sh
        if get_filename_path:
            if filename == 'createuser.sh':
                self.pgb.setValue(0)
                local_path = get_filename_path
                # 获取用户主目录
                home_directory = '/{login_user}/{shfile}'.format(login_user=self.login_user, shfile=filename)
                remote_path = home_directory
                log.logger.info('上传createuser.sh路径:{remote_path}'.format(remote_path=remote_path))
                # 创建一个询问消息框
                reply = QMessageBox.question(self, 'Question', '确定上传并执行{file}?'.format(file=filename),
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.zip_text.append('选择了文件：{file}'.format(file=filename))
                    self.start_upload_file(local_path=local_path, remote_path=remote_path)
                    # 多线程方法
                    ssh_command = 'bash /{login_user}/{shfile}'.format(login_user=self.login_user, shfile=filename)
                    self.command_thread = CommandThread(self.ssh_instance.ssh_client, ssh_command)
                    self.command_thread.commandResult.connect(lambda text: self.zip_text.append(text))
                    self.command_thread.start()
                else:
                    log.logger.info('取消选择文件{file}'.format(file=filename))
            else:
                QMessageBox.critical(self, 'File Name Error', '文件名有误！只接受createuser.sh')
        else:
            log.logger.info('点击了按钮[createuser.sh],未选择文件')

    def handle_robotzipfile(self):
        """
        处理robot.zip包逻辑
        @return:
        """
        if self.check_user_exit():
            get_filename_path, _ = QFileDialog.getOpenFileName(self, caption="选择文件", directory=self.desktop_path,
                                                               filter="Zip Files (*.zip)")
            filename = os.path.basename(get_filename_path)  # robot.zip
            if get_filename_path:
                if filename == 'robot.zip':
                    try:
                        self.pgb.setValue(0)
                        local_path = get_filename_path
                        # 获取用户主目录
                        com_response, err_response, code_response = self.ssh_instance.execute_ssh_command(
                            "grep 1100 /etc/passwd|cut -d ':' -f 1")
                        home_dir = com_response.read().decode('utf-8').replace('\n', '')
                        remote_path = '/{home_dir}/{zipfile}'.format(home_dir=home_dir, zipfile=filename)
                        log.logger.info('上传robot.zip包路径:{remote_path}'.format(remote_path=remote_path))
                        # 创建一个询问消息框
                        reply = QMessageBox.question(self, 'Question', '确定上传并部署{file}?'.format(file=filename),
                                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                        if reply == QMessageBox.Yes:
                            self.zip_text.append('选择了文件：{file}'.format(file=filename))
                            self.start_upload_file(local_path=local_path, remote_path=remote_path)
                            # 多线程方法
                            ssh_command = 'cd /{home_dir}/ && echo "解压{zipfile}中...请勿关闭工具" && unzip {zipfile} >/dev/null && cd /{home_dir}/install/ && bash install_latest.sh'.format(
                                home_dir=home_dir, zipfile=filename)
                            self.command_thread = CommandThread(self.ssh_instance.ssh_client, ssh_command)
                            self.command_thread.commandResult.connect(lambda text: self.zip_text.append(text))
                            self.command_thread.finished_signal.connect(self.handle_thread_finished)
                            self.command_thread.start()
                        else:
                            log.logger.info('取消选择文件{file}'.format(file=filename))
                    except Exception as e:
                        QMessageBox.critical(self, 'Deploy Error', f'部署异常{e}')
                else:
                    QMessageBox.critical(self, 'File Name Error', '文件名有误！只接受robot.zip')
            else:
                log.logger.info('点击了按钮[robot.zip],未选择文件')

    def handle_patrolzipfile(self):
        """
        处理patrol.zip包逻辑
        @return:
        """
        if self.check_user_exit():
            get_filename_path, _ = QFileDialog.getOpenFileName(self, caption="选择文件", directory=self.desktop_path,
                                                               filter="Zip Files (*.zip)")
            filename = os.path.basename(get_filename_path)  # patrol.zip
            if get_filename_path:
                if filename == 'patrol.zip':
                    try:
                        self.pgb.setValue(0)
                        local_path = get_filename_path
                        # 获取用户主目录
                        com_response, err_response, code_response = self.ssh_instance.execute_ssh_command(
                            "grep 1100 /etc/passwd|cut -d ':' -f 1")
                        home_dir = com_response.read().decode('utf-8').replace('\n', '')
                        remote_path = '/{home_dir}/{zipfile}'.format(home_dir=home_dir, zipfile=filename)
                        log.logger.info('上传patrol.zip包路径:{remote_path}'.format(remote_path=remote_path))
                        # 创建一个询问消息框
                        reply = QMessageBox.question(self, 'Question', '确定上传并部署{file}?'.format(file=filename),
                                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                        if reply == QMessageBox.Yes:
                            self.zip_text.append('选择了文件：{file}'.format(file=filename))
                            self.start_upload_file(local_path=local_path, remote_path=remote_path)
                            # 多线程方法
                            ssh_command = 'cd /{home_dir}/ && echo "解压{zipfile}中...请勿关闭工具" && unzip {zipfile} >/dev/null && cd /{home_dir}/install/ && bash install_latest.sh'.format(
                                home_dir=home_dir, zipfile=filename)
                            self.command_thread = CommandThread(self.ssh_instance.ssh_client, ssh_command)
                            self.command_thread.commandResult.connect(lambda text: self.zip_text.append(text))
                            self.command_thread.finished_signal.connect(self.handle_thread_finished)
                            self.command_thread.start()
                        else:
                            log.logger.info('取消选择文件{file}'.format(file=filename))
                    except Exception as e:
                        QMessageBox.critical(self, 'Deploy Error', f'部署异常{e}')
                else:
                    QMessageBox.critical(self, 'File Name Error', '文件名有误！只接受patrol.zip')
            else:
                log.logger.info('点击了按钮[patrol.zip],未选择文件')

    def slot_on_deployfile_click(self):
        """
        槽函数，处理上传文件逻辑
        @return:
        """
        if self.check_is_puresys():
            # 获取当前用户桌面
            self.desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
            btn_name = self.sender().text()
            if btn_name == 'createuser.sh':
                self.handle_createuser_shfile()
            elif btn_name == 'robot.zip':
                self.handle_robotzipfile()
            elif btn_name == 'patrol.zip':
                self.handle_patrolzipfile()
            else:
                pass

    def create_left_layout(self):
        # 左侧布局
        left_layout = QVBoxLayout()
        left_text_edit = QTextEdit()
        left_text_edit.setReadOnly(True)

        # 插入图片
        image_path = "image/bushu.png"  # 替换为你的图片路径
        image_reader = QImageReader(image_path)
        image = image_reader.read()
        if image.isNull():
            left_text_edit.setPlainText("图片加载失败")
        else:
            # 按比例缩小图片，这里设置缩放比例为 0.5（即缩小为原来的一半）
            scaled_image = image.scaled(int(image.width() * 0.5), int(image.height() * 0.5))
            cursor = QTextCursor(left_text_edit.document())
            cursor.insertBlock()  # 插入一个新段落

            format = QTextBlockFormat()
            format.setAlignment(Qt.AlignHCenter)  # 设置段落水平居中
            cursor.setBlockFormat(format)

            cursor.insertImage(scaled_image)
            left_text_edit.setTextCursor(cursor)
        left_layout.addWidget(left_text_edit)
        return left_layout

    def create_center_layout(self):
        # 中间布局
        if self.login_type == '机器人系统':
            btn_list = ['createuser.sh', 'robot.zip']
        elif self.login_type == '巡视系统':
            btn_list = ['createuser.sh', 'patrol.zip', ]
        center_layout = QVBoxLayout()
        for i in range(0, len(btn_list), 4):
            for j in range(i, min(i + 4, len(btn_list))):
                button = QPushButton(btn_list[j], self)
                button.setFixedSize(160, 50)
                center_layout.addWidget(button)
                button.clicked.connect(self.slot_on_deployfile_click)
        return center_layout

    def create_right_layout(self):
        # 右侧布局
        right_layout = QVBoxLayout()
        # 载入进度条控件
        self.pgb = QProgressBar()
        right_layout.addWidget(self.pgb)

        # 设置进度条的范围
        self.pgb.setMinimum(0)
        self.pgb.setMaximum(100)
        self.pgb.setValue(0)
        # 添加说明文本框
        self.zip_text = QTextEdit()
        self.zip_text.setReadOnly(True)
        right_layout.addWidget(self.zip_text)
        return right_layout

    def create_deployzip(self):
        """
        创建系统部署界面
        :return:
        """
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        # 创建主体水平布局
        main_layout = QHBoxLayout()

        # 左侧布局
        left_layout = self.create_left_layout()

        # 中间布局
        center_layout = self.create_center_layout()

        # 右侧布局
        right_layout = self.create_right_layout()

        # 将三个子布局添加到主水平布局中
        main_layout.addLayout(left_layout)
        main_layout.addLayout(center_layout)
        main_layout.addLayout(right_layout)
        # 将水平布局设置到中心部件上
        central_widget.setLayout(main_layout)

    def start_upload_file(self, local_path, remote_path):
        """
        文件上传方法
        @param local_path: 本地路径
        @param remote_path: 远程路径
        @return:
        """
        self.file_exec_instance.connect()
        # 上传文件
        with open(local_path, 'rb') as f:
            self.file_size = os.fstat(f.fileno()).st_size  # 获取本地文件的大小
        self.file_exec_instance.upload_file(local_path, remote_path, self.update_progress)
        self.file_exec_instance.close()

    def start_download_file(self, local_path, remote_path):
        """
        文件下载方法
        @param local_path: 本机路径
        @param remote_path: 远程路径
        @return:
        """
        self.file_exec_instance.connect()
        # 下载文件
        self.file_exec_instance.download_file(remote_path, local_path, self.update_progress)
        self.file_exec_instance.close()

    @pyqtSlot(int, int)
    def update_progress(self, transferred, total):
        """
        处理接收到的进度信息并更新到进度条上
        @param transferred:
        @param total:
        @return:
        """
        if total > 0:
            print(f"Transferred: {transferred}, Total: {total}")
            self.pgb.setValue(int(transferred * 100 / total))
        elif total == 0:
            print(f"Transferred: {transferred}, Total: {total}")
            self.pgb.setValue(int(transferred * 100 / self.file_size))
        else:
            print('total异常%s' % total)

    def set_centralWindow(self):
        """
        设置窗口大小并居中展示
        @return:
        """
        self.setWindowTitle('工作台')
        self.setGeometry(500, 700, 1600, 900)
        screen = QApplication.desktop().screenGeometry()
        window_size = self.geometry()
        x = (screen.width() - window_size.width()) // 2
        y = (screen.height() - window_size.height()) // 2
        self.move(x, y)
        # 设置窗口图标，确保替换为你的图标文件路径
        self.setWindowIcon(QIcon('icon/tools_logo.png'))

    def initStatusbar(self):
        """
        定义状态栏
        @return:
        """
        # 创建状态栏
        statusbar = self.statusBar()
        status_message = '已登录主机:{ip} 登录账号:{user}'.format(ip=self.login_ip, user=self.login_user)
        status_label = QLabel(status_message)
        status_label.setWordWrap(False)
        statusbar.addPermanentWidget(status_label)
        log.logger.info(status_message)

    def initUI(self):
        self.set_centralWindow()
        self.initStatusbar()
        self.create_deployzip()

    def closeEvent(self, event):
        """
        重写mainwindow的窗口关闭事件，关闭时顺带关闭ssh连接
        @param event:
        @return:
        """
        self.validation_window.showValidation()  # 重新显示验证窗口
        self.hide()
        event.ignore()  # 忽略关闭事件，不关闭应用程序
        self.ssh_instance.close_ssh_connection()


class Main_window(QMainWindow):
    def __init__(self, validation_window, ssh_ip, ssh_user, ssh_thread, file_exec_instance, https_port):
        """
        主操作界面
        @param validation_window: Login_window的实例
        @param ssh_ip:
        @param ssh_user:
        @param ssh_thread: 登录成功后创建的ssh实例
        """
        super().__init__()
        self.validation_window = validation_window
        self.login_ip = ssh_ip
        self.login_user = ssh_user
        self.ssh_instance = ssh_thread
        self.file_exec_instance = file_exec_instance
        self.login_https_port = https_port
        self.sysheal_check_timer = QTimer(self)
        self.sysheal_check_timer.timeout.connect(lambda: self.cron_update_check())
        self.point_filetype = 0
        self.point_belowtype = 1
        self.initUI()

    def initTab(self):
        """
        初始化tab页
        @return:
        """
        self.tabs = QTabWidget()
        # 设置QTabWidget对象为中心部件
        self.setCentralWidget(self.tabs)
        # 开启标签页的图片和关闭功能
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.tabs.removeTab)
        self.create_indexTab('首页')
        self.qactionConnectTab()
        self.is_checking = False  # 记录是否点击了

    def initMenu(self, menu_str, menu_set):
        """
        定义菜单格式，支持到三级菜单
        @param menu_str:
        @param menu_set:
        @return:
        """
        if not isinstance(menu_set, dict):
            raise ValueError("menu_set must be a dict")
        menubar = self.menuBar()
        Menu = menubar.addMenu(menu_str)  # 一级菜单
        action_list = []
        for k, v in menu_set.items():
            if v is None:
                elementAction = QAction(k, self)
                Menu.addAction(elementAction)
                action_list.append(elementAction)
            elif v:
                if not isinstance(v, list):
                    raise ValueError("menu_set.values must be a list")
                second_Menu = Menu.addMenu(k)  # 二级菜单
                for i in v:
                    elementAction = QAction(i, self)
                    second_Menu.addAction(elementAction)  # 三级action
                    action_list.append(elementAction)
        return action_list

    def initStatusbar(self):
        """
        定义状态栏
        @return:
        """
        self.get_sysInfo()
        # 创建状态栏
        statusbar = self.statusBar()
        status_message = '已登录主机:{ip} 登录账号:{user}  系统类型:{sys_type}' \
            .format(ip=self.login_ip, user=self.login_user, sys_type=self.sys_type)
        status_label = QLabel(status_message)
        status_label.setWordWrap(False)
        statusbar.addPermanentWidget(status_label)
        log.logger.info(status_message)

    def slot_show_containerstatus(self):
        """
        槽函数，展示容器状态
        @return:
        """
        sys_command = 'docker ps -a'
        com_response, err_response, code_response = self.ssh_instance.execute_ssh_command(sys_command)
        com_text = com_response.read().decode('utf-8')
        err_text = err_response.read().decode('utf-8')
        if err_text:
            QMessageBox.critical(self, 'Command Error', err_text)
            self.appstatus_text.setPlainText(com_text)
        else:
            self.appstatus_text.setPlainText(com_text)

    def slot_basic_config_click(self):
        btn_name = self.sender().text()
        if btn_name == '导入厂站与执行设备':
            self.create_fac_excel(btn_name)
        elif btn_name == '导入主机与平台':
            self.create_host_excel(btn_name)
        elif btn_name == '导入点表':
            self.create_point_excel(btn_name)
        else:
            pass

    def slot_show_dockerlogs(self):
        """
        槽函数，展示容器日志
        @return:
        """

        btn_name = self.sender().text()
        new_win = NewWindow(btn_name, self)
        new_win.show()
        ssh_command = 'docker logs -f --tail 100 {containername}'.format(containername=btn_name)
        self.command_thread = CommandThread(self.ssh_instance.ssh_client, ssh_command)
        self.command_thread.commandResult.connect(new_win.append_text)
        self.command_thread.start()

    def slot_show_sysService(self):
        """
        槽函数，展示Linux服务
        @return:
        """
        btn = self.sender()
        service_name = btn.text()
        # 创建一个询问消息框
        reply = QMessageBox.question(self, 'Question', '确定重启服务{svc}?'.format(svc=service_name),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            sys_command = 'sudo systemctl  restart {servicename}  && echo -e "--------{servicename} status--------\n" \
                       && sudo systemctl status {servicename}'.format(servicename=service_name)
            com_response, err_response, code_response = self.ssh_instance.execute_ssh_command(sys_command)
            com_text = com_response.read().decode('utf-8')
            err_text = err_response.read().decode('utf-8')
            if err_text:
                QMessageBox.critical(self, 'Command Error', err_text)
                self.sys_text.setPlainText(err_text)
            else:
                self.sys_text.setPlainText(com_text)
        else:
            log.logger.info('slot_show_sysService not clicked')

    def slot_show_rebuildlogs(self):
        """
        槽函数，构建容器
        @return:
        """
        btnname = self.sender().text()
        # 创建一个询问消息框
        reply = QMessageBox.question(self, 'Question', '确定构建{btn}?'.format(btn=btnname),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if btnname == 'rebuild all':
                sys_command = 'bash ~/deploy-script/shell/rebuild.sh'
            else:
                sys_command = 'bash ~/deploy-script/shell/rebuild.sh {containername}'.format(
                    containername=btnname)

            com_response, err_response, code_response = self.ssh_instance.execute_ssh_command(sys_command)
            com_text = com_response.read().decode('utf-8')
            err_text = err_response.read().decode('utf-8')
            if err_text:
                self.rebuild_text.setPlainText(err_text)
            else:
                self.rebuild_text.setPlainText(com_text)
        else:
            log.logger.info('slot_show_rebuildlogs not clicked')

    def slot_show_restartlogs(self):
        """
        槽函数，构建容器
        @return:
        """
        btnname = self.sender().text()
        # 创建一个询问消息框
        reply = QMessageBox.question(self, 'Question', '确定重启{btn}?'.format(btn=btnname),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if btnname == 'restart all':
                sys_command = 'bash ~/deploy-script/shell/restart.sh'
            else:
                sys_command = 'docker restart {containername}'.format(containername=btnname)

            com_response, err_response, code_response = self.ssh_instance.execute_ssh_command(sys_command)
            com_text = com_response.read().decode('utf-8')
            err_text = err_response.read().decode('utf-8')
            if err_text:
                self.restart_text.setPlainText(err_text)
            else:
                self.restart_text.setPlainText(com_text)
        else:
            log.logger.info('slot_show_restartlogs not clicked')

    def start_upload_file(self, local_path, remote_path):
        """
        文件上传方法
        @param local_path: 本地路径
        @param remote_path: 远程路径
        @return:
        """
        self.file_exec_instance.connect()
        # 上传文件
        with open(local_path, 'rb') as f:
            self.file_size = os.fstat(f.fileno()).st_size  # 获取本地文件的大小
        self.file_exec_instance.upload_file(local_path, remote_path, self.update_progress)
        self.file_exec_instance.close()

    def start_download_file(self, local_path, remote_path):
        """
        文件下载方法
        @param local_path: 本机路径
        @param remote_path: 远程路径
        @return:
        """
        self.file_exec_instance.connect()
        # 下载文件
        self.file_exec_instance.download_file(remote_path, local_path, self.update_progress)
        self.file_exec_instance.close()

    @pyqtSlot(int, int)
    def update_progress(self, transferred, total):
        """
        处理接收到的进度信息并更新到进度条上
        @param transferred:
        @param total:
        @return:
        """
        if total > 0:
            print(f"Transferred: {transferred}, Total: {total}")
            self.pgb.setValue(int(transferred * 100 / total))
        elif total == 0:
            print(f"Transferred: {transferred}, Total: {total}")
            self.pgb.setValue(int(transferred * 100 / self.file_size))
        else:
            print('total异常%s' % total)

    def handle_jarfile(self):
        """
        处理jar包逻辑
        @return:
        """
        get_filename_path, _ = QFileDialog.getOpenFileName(self, caption="选择文件", directory=self.desktop_path,
                                                           filter="Jar Files (*.jar)")
        if get_filename_path:
            self.pgb.setValue(0)
            filename = os.path.basename(get_filename_path)  # patrol-task.jar
            svc_name = os.path.splitext(filename)[0]  # patrol-task
            local_path = get_filename_path
            # 获取用户主目录
            home_directory = '/{login_user}/'.format(login_user=self.login_user)
            remote_path = os.path.join(home_directory, 'chiebot-docker-app/backend/jar/{jar}'.format(jar=filename))
            log.logger.info('上传jar包路径:{remote_path}'.format(remote_path=remote_path))
            # 创建一个询问消息框
            reply = QMessageBox.question(self, 'Question', '确定升级{file}?'.format(file=filename),
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.zip_text.append('选择了文件：{file}'.format(file=filename))
                com_response, err_response, code_response = self.ssh_instance.execute_ssh_command('docker stop {svc} && cd ~/chiebot-docker-app/backend/jar \
                     && mv {svc}.jar {svc}.bak'.format(svc=svc_name))
                err_text = err_response.read().decode('utf-8')
                if err_text:
                    self.zip_text.append(err_text)
                    QMessageBox.critical(self, 'Command Execution Failed',
                                         '已停止上传{svc}.jar,联系开发查看后重新更新'.format(svc=svc_name))
                else:
                    self.zip_text.append('备份{svc}.jar完成'.format(svc=svc_name))
                    self.start_upload_file(local_path=local_path, remote_path=remote_path)
                    self.ssh_instance.execute_ssh_command('docker start {svc}'.format(svc=svc_name))
                    self.zip_text.append('启动服务：{svc}'.format(svc=svc_name))
            else:
                log.logger.info('取消选择文件{file}'.format(file=filename))
        else:
            log.logger.info('点击了按钮[jar],未选择文件')

    def handle_distfile(self):
        """
        处理dist包逻辑
        @return:
        """
        get_filename_path, _ = QFileDialog.getOpenFileName(self, caption="选择文件", directory=self.desktop_path,
                                                           filter="Zip Files (*.zip)")
        filename = os.path.basename(get_filename_path)  # dist.zip
        if get_filename_path:
            if filename == 'dist.zip':
                self.pgb.setValue(0)
                local_path = get_filename_path
                # 获取用户主目录
                home_directory = '/{login_user}/'.format(login_user=self.login_user)
                remote_path = os.path.join(home_directory, 'chiebot-docker-app/frontend/{dist}'.format(dist=filename))
                log.logger.info('上传dist包路径:{remote_path}'.format(remote_path=remote_path))
                now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                # 创建一个询问消息框
                reply = QMessageBox.question(self, 'Question', '确定升级{file}?'.format(file=filename),
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.zip_text.append('选择了文件：{file}'.format(file=filename))
                    self.start_upload_file(local_path=local_path, remote_path=remote_path)
                    # 多线程方法
                    ssh_command = 'echo "停止服务patrol-ui" && docker stop patrol-ui && cd ~/chiebot-docker-app/frontend/ \
                         && mv dist dist.bak_{bakdate} && unzip {dist} && docker start patrol-ui && \
                                  echo "启动服务patrol-ui"'.format(bakdate=now, dist=filename)
                    self.command_thread = CommandThread(self.ssh_instance.ssh_client, ssh_command)
                    self.command_thread.commandResult.connect(lambda text: self.zip_text.append(text))
                    self.command_thread.start()
                else:
                    log.logger.info('取消选择文件{file}'.format(file=filename))
            else:
                QMessageBox.critical(self, 'File Name Error', '文件名有误！只接受dist.zip')
        else:
            log.logger.info('点击了按钮[dist],未选择文件')

    def handle_zipfile(self):
        """
        处理upgrade包逻辑
        @return:
        """
        get_filename_path, _ = QFileDialog.getOpenFileName(self, caption="选择文件", directory=self.desktop_path,
                                                           filter="Zip Files (*.zip)")
        filename = os.path.basename(get_filename_path)  # upgrade.zip
        shfile = 'file_unzip.sh' if self.login_user == 'patrol' else 'robot_file_unzip.sh' if self.login_user == 'robot' else None
        if get_filename_path:
            if filename == 'upgrade.zip':
                self.pgb.setValue(0)
                local_path = get_filename_path
                # 获取用户主目录
                home_directory = '/{login_user}/{upgradefile}'.format(login_user=self.login_user, upgradefile=filename)
                remote_path = home_directory
                log.logger.info('上传upgrade包路径:{remote_path}'.format(remote_path=remote_path))
                # 创建一个询问消息框
                reply = QMessageBox.question(self, 'Question', '确定升级{file}?'.format(file=filename),
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.zip_text.append('选择了文件：{file}'.format(file=filename))
                    com_response, err_response, code_response = self.ssh_instance.execute_ssh_command(
                        'ls /{login_user}/{shfile}'
                        .format(login_user=self.login_user, shfile=shfile))
                    com_text = com_response.read().decode('utf-8')
                    err_text = err_response.read().decode('utf-8')
                    if err_text:
                        self.zip_text.append(err_text)
                        QMessageBox.critical(self, 'File Not Exit', '执行文件{shfile}在{ip}上未找到，上传{shfile}后重试!'
                                             .format(shfile=shfile, ip=self.login_ip))
                    elif com_text.replace('\n', '') == '/{login_user}/{shfile}'.format(login_user=self.login_user,
                                                                                       shfile=shfile):
                        self.zip_text.append(com_text)
                        self.start_upload_file(local_path=local_path, remote_path=remote_path)
                        # 多线程方法
                        ssh_command = 'bash /{login_user}/{shfile}'.format(login_user=self.login_user, shfile=shfile)
                        self.command_thread = CommandThread(self.ssh_instance.ssh_client, ssh_command)
                        self.command_thread.commandResult.connect(lambda text: self.zip_text.append(text))
                        self.command_thread.start()
                else:
                    log.logger.info('取消选择文件{file}'.format(file=filename))
            else:
                QMessageBox.critical(self, 'File Name Error', '文件名有误！只接受upgrade.zip')
        else:
            log.logger.info('点击了按钮[upgrade],未选择文件')

    def slot_on_updatefile_click(self):
        """
        槽函数，处理上传文件逻辑
        @return:
        """
        # 获取当前用户桌面
        self.desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
        btn_name = self.sender().text()
        if btn_name == 'jar':
            self.handle_jarfile()
        elif btn_name == 'dist':
            self.handle_distfile()
        elif btn_name == 'upgrade':
            self.handle_zipfile()
        else:
            pass

    def set_centralWindow(self):
        """
        设置窗口大小并居中展示
        @return:
        """
        self.setWindowTitle('工作台')
        self.setGeometry(500, 700, 1600, 900)
        screen = QApplication.desktop().screenGeometry()
        window_size = self.geometry()
        x = (screen.width() - window_size.width()) // 2
        y = (screen.height() - window_size.height()) // 2
        self.move(x, y)
        # 设置窗口图标，确保替换为你的图标文件路径
        self.setWindowIcon(QIcon('icon/tools_logo.png'))

    def slot_index_button_menu(self):
        # 获取触发动作的文本，即标签页标题
        tab_title = self.sender().text()
        tabs_count = self.tabs.count()
        for i in range(tabs_count):
            if self.tabs.tabText(i) == tab_title:
                self.tabs.setCurrentIndex(i)
                return
        index_menu_dict = {
            '配置基础数据': self.create_basic_configTab,
            '系统健康状态检查': self.create_SysHealthTab,
            '应用日志': self.create_appLogsTab,
            '重启应用': self.create_restartTab,
            '应用状态': self.create_appstatusTab,
            '系统更新': self.create_updatezipTab,
        }
        index_menu_dict[tab_title](tab_title)

    def show_check_progress(self):
        fac_progress_ulr = 'https://{ip}:{https_port}/account/facBasic/getImportProgressNoToken'.format(
            ip=self.login_ip, https_port=self.login_https_port)
        result = self.get_queryCheckResult(fac_progress_ulr)
        if result:
            total_progress = result['data']['progress']
            import_status = result['data']['status']  # 导入状态(0:导入结束，1:正在导入)
            if import_status == '1':
                fac_status, robot_status, drone_status, nvr_status, camera_status, audio_status = ['0'] * 6
            else:
                fac_status, robot_status, drone_status, nvr_status, camera_status, audio_status = result['data'][
                    'isSuccess'].split(',')
            status_mapping = {'0': '⌛ 导入中', '1': '✅ 导入成功'}
            output = f"""
            <p style="font-size: 32px;">导入总进度：{total_progress}</p>
            <p style="font-size: 16px;">厂站：{status_mapping[fac_status]}&nbsp;&nbsp;机器人：{status_mapping[robot_status]}&nbsp;&nbsp;无人机：{status_mapping[drone_status]}</p>
            <p style="font-size: 16px;">NVR：{status_mapping[nvr_status]}&nbsp;&nbsp;摄像机：{status_mapping[camera_status]}&nbsp;&nbsp;拾音器：{status_mapping[audio_status]}</p>
            <p style="font-size: 16px;"></p>
            """
            self.bc_text.append(output)

    def format_button(self, btn, type):
        if type == 0:
            btn.setEnabled(True)
            btn.setStyleSheet("background-color: #007BFF; color: white;")
        elif type == 1:
            btn.setEnabled(False)
            btn.setStyleSheet("")
            QApplication.processEvents()  # 强制刷新UI

    def import_fac_excel(self):
        self.format_button(self.fac_confirm_button, type=1)
        fac_filepath = self.fac_dialog.get_file_path()
        if fac_filepath:
            fac_import_ulr = 'https://{ip}:{https_port}/account/facBasic/importBasicAccountNoToken'.format(
                ip=self.login_ip, https_port=self.login_https_port)
            https_post_request = HttpsPostRequest()
            with open(fac_filepath, 'rb') as file:
                files = {'file': file}
                result = https_post_request.send_request(fac_import_ulr, files=files).json()
            fac_import_code = result['code']
            error_message = result['message']
            if fac_import_code == 200:
                QMessageBox.information(self, '文件导入', '导入成功！')
            elif fac_import_code == 1:
                templatefile_path = result['data']
                error_templatefile_url = 'https://{ip}:{https_port}{tfp}'.format(ip=self.login_ip,
                                                                                 https_port=self.login_https_port,
                                                                                 tfp=templatefile_path)
                HttpsRequest().download_file(error_templatefile_url)
            else:
                QMessageBox.critical(self, '接口错误', error_message)
            self.show_check_progress()
        else:
            QMessageBox.critical(self, '文件缺失', '先上传Excel文件再重新点击确定')
        self.fac_dialog.raise_()  # 让对话框重新回到最上层
        self.format_button(self.fac_confirm_button, type=0)

    def slot_btn_fac(self):
        btn_name = self.sender().text()
        if btn_name == '查看进度':
            self.show_check_progress()
        elif btn_name == '取消':
            self.fac_dialog.reject()
        elif btn_name == '确定':
            self.import_fac_excel()

    def create_fac_excel(self, dialog_title):
        self.fac_dialog = ModalDialog(title=dialog_title, ip=self.login_ip, https_port=self.login_https_port,
                                      template_name='下载导入厂站与执行设备模板', parent=self)
        fac_main_layout = self.fac_dialog.main_layout

        # 创建水平布局用于放置按钮
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignRight)
        btn_list = ['查看进度', '取消', '确定']
        for j in btn_list:
            button = QPushButton(j, self)
            if j == "确定":
                self.fac_confirm_button = button
                self.format_button(btn=self.fac_confirm_button, type=0)
            button_layout.addWidget(button)
            button.clicked.connect(self.slot_btn_fac)

        fac_main_layout.addLayout(button_layout)
        # self.fac_dialog.show()    # 非模态显示对话框
        self.fac_dialog.exec_()  # 以模态方式显示

    def import_host_excel(self):
        self.format_button(btn=self.host_confirm_button, type=1)
        host_filepath = self.host_dialog.get_file_path()
        if host_filepath:
            host_import_ulr = 'https://{ip}:{https_port}/account/dataInit/importSysInterfaceExcelNoToken'.format(
                ip=self.login_ip, https_port=self.login_https_port)
            https_post_request = HttpsPostRequest()
            with open(host_filepath, 'rb') as file:
                files = {'file': file}
                result = https_post_request.send_request(host_import_ulr, files=files).json()
            error_message = result['message']
            host_import_code = result['code']
            if host_import_code == 200:
                QMessageBox.information(self, '文件导入', '导入成功！')
            elif host_import_code == 1:
                templatefile_path = result['data']
                error_templatefile_url = 'https://{ip}:{https_port}{tfp}'.format(ip=self.login_ip,
                                                                                 https_port=self.login_https_port,
                                                                                 tfp=templatefile_path)
                HttpsRequest().download_file(error_templatefile_url)
            else:
                QMessageBox.critical(self, '接口错误', error_message)
        else:
            QMessageBox.critical(self, '文件缺失', '先上传Excel文件再重新点击确定')
        self.host_dialog.raise_()  # 让对话框重新回到最上层
        self.format_button(btn=self.host_confirm_button, type=0)

    def slot_btn_host(self):
        btn_name = self.sender().text()
        if btn_name == '取消':
            self.host_dialog.reject()
        elif btn_name == '确定':
            self.import_host_excel()

    def create_host_excel(self, dialog_title):
        self.host_dialog = ModalDialog(ip=self.login_ip, https_port=self.login_https_port, title=dialog_title,
                                       template_name='下载导入主机与平台模板', parent=self)
        host_main_layout = self.host_dialog.main_layout

        # 创建水平布局用于放置按钮
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignRight)
        btn_list = ['取消', '确定']
        for j in btn_list:
            button = QPushButton(j, self)
            if j == "确定":
                self.host_confirm_button = button
                self.format_button(btn=self.host_confirm_button, type=0)
            button_layout.addWidget(button)
            button.clicked.connect(self.slot_btn_host)

        host_main_layout.addLayout(button_layout)
        # self.host_dialog.show()    # 非模态显示对话框
        self.host_dialog.exec_()  # 以模态方式显示

    def Check_HostAndActuator(self):
        if self.host_combo.currentIndex() != -1 and self.device_combo.currentIndex() != -1:
            host_text = self.host_combo.currentText()
            actuator_text = self.device_combo.currentText()
            res_id_list = []
            # 获取下级主机ID
            if self.robot_radio.isChecked():
                dict_host = self.get_belowmachine_info(query_type='dicttype', below_restype=1)
            else:
                dict_host = self.get_belowmachine_info(query_type='dicttype', below_restype=2)
            belowmachine_id = dict_host[host_text]
            # 获取执行器ID
            dict_actuator = self.get_actuator_info(query_type='dicttype')
            actuator_id = dict_actuator[actuator_text]
            # [下级主机ID, 执行器ID]
            res_id_list.append(belowmachine_id)
            res_id_list.append(actuator_id)
            return res_id_list
        else:
            return None

    def import_point_excel(self, point_filepath, deviceimport_data):
        deviceimport_url = 'https://{ip}:{https_port}/account/deviceTree/importDeviceExcelNoToken'.format(
            ip=self.login_ip, https_port=self.login_https_port)
        https_post_request = HttpsPostRequest()
        with open(point_filepath, 'rb') as file:
            files = {'file': file}
            result = https_post_request.send_request(url=deviceimport_url, data=deviceimport_data, files=files).json()
        error_message = result['message']
        host_import_code = result['code']
        if host_import_code == 200:
            QMessageBox.information(self, '文件导入', '导入成功！')
        elif host_import_code == 1:
            templatefile_path = result['data']
            error_templatefile_url = 'https://{ip}:{https_port}{tfp}'.format(ip=self.login_ip,
                                                                             https_port=self.login_https_port,
                                                                             tfp=templatefile_path)
            HttpsRequest().download_file(error_templatefile_url)
        else:
            QMessageBox.critical(self, '接口错误', error_message)

    def slot_btn_point(self):
        btn_name = self.sender().text()
        if btn_name == '取消':
            self.point_dialog.reject()
        elif btn_name == '确定':
            self.format_button(btn=self.point_confirm_button, type=1)
            current_fac_name = self.station_combo.currentText()
            point_filepath = self.point_dialog.get_file_path()
            if point_filepath and self.station_combo.currentIndex() != -1:
                if self.point_filetype == 0:
                    fac_info_dict = self.get_facinfo('dicttype')
                    deviceimport_data = {'type': self.point_filetype, 'stationId': fac_info_dict[current_fac_name]}
                    self.import_point_excel(point_filepath=point_filepath, deviceimport_data=deviceimport_data)
                else:
                    id_list = self.Check_HostAndActuator()
                    if id_list is None:
                        QMessageBox.critical(self, '错误', '下级主机跟执行器都选择后再导入点位')
                    else:
                        belowmachine_id, actuator_id = id_list
                        deviceimport_data = {'type': self.point_filetype, 'belowType': self.point_belowtype,
                                             'belowId': belowmachine_id, 'actuatorId': actuator_id}
                        self.import_point_excel(point_filepath=point_filepath, deviceimport_data=deviceimport_data)
            else:
                QMessageBox.critical(self, '错误', '上传点位文件并选择厂站后重试')
            self.point_dialog.raise_()  # 让对话框重新回到最上层
            self.format_button(btn=self.point_confirm_button, type=0)

    def get_facinfo(self, fac_restype):
        facinfo_url = 'https://{ip}:{https_port}/account/facInfo/listNoToken'.format(ip=self.login_ip,
                                                                                     https_port=self.login_https_port)
        result = self.get_queryCheckResult(facinfo_url)['data']
        fac_info_list = []
        fac_info_dict = {}
        for fac in result:
            fac_info_list.append(fac['stationName'])
            fac_info_dict[fac['stationName']] = fac['id']
        if fac_restype == 'listtype':
            return fac_info_list
        elif fac_restype == 'dicttype':
            return fac_info_dict
        else:
            return

    def get_belowmachine_info(self, below_restype, query_type):
        belowinfo_url = 'https://{ip}:{https_port}/account/belowMachine/listNoToken?type={type}'.format(
            ip=self.login_ip,
            https_port=self.login_https_port, type=below_restype)
        result = self.get_queryCheckResult(belowinfo_url)['data']
        below_name_list = []
        below_info_dict = {}
        for belowma in result:
            below_name_list.append(belowma['deviceName'])
            below_info_dict[belowma['deviceName']] = belowma['id']
        if query_type == 'listtype':
            return below_name_list
        elif query_type == 'dicttype':
            return below_info_dict
        else:
            return

    def set_import_type(self):
        btn_name = self.sender().text()
        if btn_name == '本地点位':
            self.point_filetype = 0
            self.sub_group.setVisible(False)
        elif btn_name == '下级点位':
            self.point_filetype = 1
            """当导入类型切换时更新显示状态"""
            self.sub_group.setVisible(True)

    def slot_download_point_templatefile(self):
        if self.point_filetype == 0:
            download_file = '本地点位模板.xlsx'
        else:
            download_file = '下级模板.xlsx'
        url = 'https://{ip}:{https_port}/account/deviceTree/downLoadExcelTemplateNoToken'.format(ip=self.login_ip,
                                                                                                 https_port=self.login_https_port)
        data = {'fileType': self.point_filetype}
        https_post_request = HttpsPostRequest()
        response = https_post_request.send_request(url=url, data=data)
        # 获取桌面路径
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        file_path = os.path.join(desktop_path, download_file)

        # 创建一个询问消息框
        reply = QMessageBox.question(self, 'Question',
                                     '下载后将覆盖桌面上原来{file},是否继续?'.format(file=download_file),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            # 以二进制写入模式打开文件并保存内容
            with open(file_path, 'wb') as file:
                file.write(response.content)
                QMessageBox.information(self, '文件下载完成', f"{download_file}已下载至桌面")
        else:
            self.point_dialog.raise_()

    def get_actuator_info(self, query_type):
        text = self.host_combo.currentText()
        if self.robot_radio.isChecked():
            dict_robot = self.get_belowmachine_info(query_type='dicttype', below_restype=1)
            belowmachine_id_list = []
            belowmachine_id = dict_robot[text]
            belowmachine_id_list.append(belowmachine_id)
            actuator_url = 'https://{ip}:{https_port}/account/robot/listsNoToken'.format(
                ip=self.login_ip,
                https_port=self.login_https_port)
            https_post_request = HttpsPostRequest()
            result = https_post_request.send_request(url=actuator_url, json=belowmachine_id_list).json()['data']
        else:
            dict_drone = self.get_belowmachine_info(query_type='dicttype', below_restype=2)
            belowmachine_id = dict_drone[text]
            actuator_url = 'https://{ip}:{https_port}/account/drone/listWithMulNoToken?belowIds={id}'.format(
                ip=self.login_ip, https_port=self.login_https_port, id=belowmachine_id)
            result = self.get_queryCheckResult(actuator_url)['data']
        actuator_name_list = []
        actuator_info_dict = {}
        for actuatorma in result:
            actuator_name_list.append(actuatorma['deviceName'])
            actuator_info_dict[actuatorma['deviceName']] = actuatorma['id']
        if query_type == 'listtype':
            return actuator_name_list
        elif query_type == 'dicttype':
            return actuator_info_dict
        else:
            return

    def get_selectionchange_text(self):
        actuator_list = self.get_actuator_info('listtype')
        self.device_combo.clear()
        self.device_combo.addItems(actuator_list)
        self.device_combo.setCurrentIndex(-1)  # 设置默认索引为空选项

    def on_host_type_changed(self):
        """当下级主机类型切换时更新标签和选项"""
        self.host_combo.clear()
        self.device_combo.clear()
        if self.robot_radio.isChecked():
            # 机器人主机
            self.host_label.setText('机器人主机：')
            self.device_label.setText('机器人：')
            list_robot = self.get_belowmachine_info(query_type='listtype', below_restype=1)
            self.host_combo.addItems(list_robot)
            self.host_combo.setCurrentIndex(-1)  # 设置默认索引为空选项
            self.point_belowtype = 1
        else:
            # 无人机主机
            self.host_label.setText('无人机主机：')
            self.device_label.setText('无人机：')
            list_drone = self.get_belowmachine_info(query_type='listtype', below_restype=2)
            self.host_combo.addItems(list_drone)
            self.host_combo.setCurrentIndex(-1)  # 设置默认索引为空选项
            self.point_belowtype = 2

    def create_point_excel(self, dialog_title):
        self.point_dialog = PointModalDialog(title=dialog_title, parent=self)
        point_main_layout = self.point_dialog.main_layout
        template_name = '下载巡视点位模板'

        # 创建水平布局放置单选按钮和超链接
        link_layout = QHBoxLayout()
        # 添加单选按钮组
        radio_label = QLabel("导入点位：", self)
        link_layout.addWidget(radio_label)

        radio_list = ['本地点位', '下级点位']
        for j in radio_list:
            radio_btn = QRadioButton(j, self)
            if j == '本地点位':
                radio_btn.setChecked(True)
            radio_btn.clicked.connect(lambda: self.set_import_type())
            link_layout.addWidget(radio_btn)

        link_layout.addStretch()  # 添加伸缩项使超链接靠右

        # 添加超链接文字
        link_label = QLabel(f'<a href="#">{template_name}</a>')
        link_label.setOpenExternalLinks(False)
        link_label.setCursor(QCursor(Qt.PointingHandCursor))
        link_label.setAlignment(Qt.AlignRight)
        link_label.linkActivated.connect(self.slot_download_point_templatefile)
        link_layout.addWidget(link_label)
        point_main_layout.addLayout(link_layout)

        # 厂站表格布局（常显）
        station_group = QGroupBox("厂站信息")
        station_layout = QFormLayout()

        station_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)  # 表单标签的右对齐 + 垂直居中
        # 设置占位文本和样式
        self.station_combo = QComboBox()
        station_list = self.get_facinfo('listtype')
        self.station_combo.addItems(station_list)
        self.station_combo.setCurrentIndex(-1)  # 设置默认索引为空选项

        station_layout.addRow('厂站：', self.station_combo)
        station_group.setLayout(station_layout)
        point_main_layout.addWidget(station_group)

        # 下级点位表格布局（默认隐藏）
        self.sub_group = QGroupBox("下级点位信息")
        sub_layout = QFormLayout()
        sub_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # 第二行：下级主机类型选择
        host_type_layout = QHBoxLayout()

        self.robot_radio = QRadioButton('机器人主机')
        self.robot_radio.setChecked(True)  # 默认选择机器人主机
        self.robot_radio.clicked.connect(self.on_host_type_changed)

        self.drone_radio = QRadioButton('无人机主机')
        self.drone_radio.clicked.connect(self.on_host_type_changed)

        host_type_layout.addWidget(self.robot_radio)
        host_type_layout.addWidget(self.drone_radio)
        host_type_layout.addStretch()  # 添加伸缩项使按钮靠左
        sub_layout.addRow('下级主机类型：', host_type_layout)

        # 第三行：主机选择
        list_robot = self.get_belowmachine_info(query_type='listtype', below_restype=1)
        self.host_label = QLabel('机器人主机：')
        self.host_combo = QComboBox()
        self.host_combo.addItems(list_robot)
        self.host_combo.setCurrentIndex(-1)  # 设置默认索引为空选项
        self.host_combo.activated[str].connect(self.get_selectionchange_text)
        sub_layout.addRow(self.host_label, self.host_combo)

        # 第四行：设备选择
        self.device_label = QLabel('机器人：')
        self.device_combo = QComboBox()
        self.device_combo.addItems(list_robot)
        self.device_combo.setCurrentIndex(-1)  # 设置默认索引为空选项
        sub_layout.addRow(self.device_label, self.device_combo)

        self.sub_group.setLayout(sub_layout)
        point_main_layout.addWidget(self.sub_group)

        # 初始设置下级点位表格隐藏
        self.sub_group.setVisible(False)
        # 设置布局的间距
        point_main_layout.setSpacing(20)

        # 创建水平布局用于放置按钮
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignRight)
        btn_list = ['取消', '确定']
        for j in btn_list:
            button = QPushButton(j, self)
            if j == "确定":
                self.point_confirm_button = button
                self.format_button(btn=self.point_confirm_button, type=0)
            button_layout.addWidget(button)
            button.clicked.connect(self.slot_btn_point)

        point_main_layout.addLayout(button_layout)
        # self.point_dialog.show()
        self.point_dialog.exec_()

    def get_queryCheckResult(self, url):
        https_request = HttpsRequest()
        result = https_request.send_request(url)
        return result

    def get_checktext(self):
        query_result_url = 'https://{ip}:{https_port}/actor/healthCheck/queryCheckResultNoToken'.format(
            ip=self.login_ip, https_port=self.login_https_port)
        result = self.get_queryCheckResult(query_result_url)
        if result:
            try:
                checkTotal = result['data']['checkTotal']
                checkAbnormal = result['data']['checkAbnormal']
                checkNormal = result['data']['checkNormal']
                checkProgress = float(result['data']['checkProgress'][:-1])
                check_text = (
                    f"检查共{checkTotal}项 <span style='color: red; font-weight: bold;'>异常{checkAbnormal}项</span> 正常{checkNormal}项")
            except KeyError:
                log.logger.error("未获取到统计值")
        else:
            check_text = "检查0项 异常0项 正常0项"
        return check_text, checkProgress

    def cron_update_check(self):
        check_text = self.get_checktext()[0]
        self.check_count_label.setText(check_text)
        int_check_progress = int(self.get_checktext()[1])
        self.sht_pgb.setValue(int_check_progress)
        self.sht_pgb.setFormat("{0:.2f}%".format(self.get_checktext()[1]))
        self.create_SysHealthdata_gblayout(self.sysheal_scroll_layout)
        if int_check_progress == 100:
            self.check_btn.setText("开始")
            self.is_checking = False
            self.stop_syscheck()

    def start_syscheck(self):
        url_start_check = 'https://{ip}:{https_port}/actor/healthCheck/startCheckNoToken'.format(ip=self.login_ip,
                                                                                                 https_port=self.login_https_port)
        self.get_queryCheckResult(url_start_check)
        self.sysheal_check_timer.start(2000)

    def stop_syscheck(self):
        url_stop_check = 'https://{ip}:{https_port}/actor/healthCheck/stopCheckNoToken'.format(ip=self.login_ip,
                                                                                               https_port=self.login_https_port)
        self.get_queryCheckResult(url_stop_check)
        self.sysheal_check_timer.stop()

    def slot_btn_check(self):
        if self.check_btn.text() == "开始":
            self.check_btn.setText("停止")
            self.is_checking = True
            self.start_syscheck()
        else:
            self.check_btn.setText("开始")
            self.is_checking = False
            self.stop_syscheck()

    def clear_layout(self, layout, keep_widgets=0):
        """
        安全清空布局控件（支持保留前keep_widgets个控件）
        @param keep_widgets: 保留前N个控件（用于保留标题等固定元素）
        """
        while layout.count() > keep_widgets:
            item = layout.takeAt(keep_widgets)  # 从第keep_widgets个开始移除
            if item.widget():
                item.widget().deleteLater()  # 异步销毁，避免UI卡顿
            # elif item.layout():
            #     self.clear_layout(item.layout())  # 递归清空子布局

    def set_fonts_style(self, checkResultType, label):
        if checkResultType == 0:
            label.setText("❌ 异常")
            label.setStyleSheet("color: red;")
        elif checkResultType == 1:
            label.setText("✅ 正常")
            label.setStyleSheet("color: green;")
        elif checkResultType == 2:
            label.setText("💡 修复完成")
            label.setStyleSheet("color: green;")
        elif checkResultType == 3:
            label.setText("⚠️ 修复失败")
            label.setStyleSheet("color: orange;")

    # 查看更多超链接点击处理函数
    def handle_more_link_clicked(self, check_type):
        more_window = DataTableWindow(checktype=check_type, ip=self.login_ip, https_port=self.login_https_port, parent=self)
        more_window.exec_()


    # 修复按钮点击事件处理函数
    def handle_repair_click(self, value):
        renovate_id = value.get('id')
        renovate_result_url = 'https://{ip}:{https_port}/actor/healthCheck/renovateByIdNoToken?id={id}'.format(
            ip=self.login_ip, https_port=self.login_https_port, id=renovate_id)
        self.get_queryCheckResult(renovate_result_url)
        self.cron_update_check()

    def set_linklayout(self):
        # 创建一个水平布局用于标题行
        header_layout = QHBoxLayout()
        # 在标题下边添加一个 QLabel 显示额外信息
        if not self.checkStatisticDesc:
            extra_label = QLabel('<span style="color: green; font-weight: bold;">不存在异常项</span>')
        else:
            extra_label = QLabel(f'<span style="color: red; font-weight: bold;">{self.checkStatisticDesc}</span>')
        extra_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)  # 对齐到左上角
        extra_label.setTextFormat(Qt.RichText)  # 开启富文本解析
        header_layout.addWidget(extra_label)

        allow_checkTypeDesc_list = ['点位', '相机', 'NVR', '机器人', '无人机', '拾音器', '值配置', '位置状态类型']
        if self.checkTypeDesc in allow_checkTypeDesc_list:
            # 创建查看更多超链接
            more_link = QLabel('<a href="#">查看更多</a>')
            more_link.setAlignment(Qt.AlignTop | Qt.AlignRight)  # 对齐到右上角
            more_link.setTextFormat(Qt.RichText)
            more_link.setTextInteractionFlags(Qt.TextBrowserInteraction)
            more_link.setOpenExternalLinks(False)
            # 将超链接点击事件绑定到处理函数
            more_link.linkActivated.connect(lambda _, ct=self.checkType: self.handle_more_link_clicked(ct))
            header_layout.addWidget(more_link)

        return header_layout

    def set_gridlayout(self, data):
        # 设置网格布局展示数据
        grid_layout = QGridLayout()
        list_details = data['details']
        # 预处理数据，提前计算修复链接信息
        for pre_value in list_details:
            pre_value['repair_link'] = ''  # 默认空值
            if pre_value.get('renovate') is True:
                pre_value['repair_link'] = '<a href="#">修复</a>'

        for idx, value in enumerate(list_details):
            # 将数据添加到网格布局中
            checkResultType = value['checkResultType']
            label1 = QLabel(value['checkItemDesc'])
            label1.setTextInteractionFlags(label1.textInteractionFlags() | Qt.TextSelectableByMouse)  # 让标签文本可被选中和复制
            label2 = QLabel(value['checkContentDesc'])
            label3 = QLabel(value['checkContent'])
            label4 = QLabel(value['checkResultAbnormalReason'])
            label5 = QLabel(value['checkResultTypeDesc'])
            self.set_fonts_style(checkResultType, label5)
            # 添加第六列：修复链接（使用预处理结果）
            label6 = QLabel()
            label6.setText(value['repair_link'])
            if value['repair_link']:
                label6.setOpenExternalLinks(False)
                label6.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextBrowserInteraction)
                label6.linkActivated.connect(lambda _, v=value: self.handle_repair_click(v))
            grid_layout.addWidget(label1, idx, 0)  # 把lable1放在第1列，第idx行
            grid_layout.addWidget(label2, idx, 1)  # 把lable2放在第2列，第idx行
            grid_layout.addWidget(label3, idx, 2)
            grid_layout.addWidget(label4, idx, 3)
            grid_layout.addWidget(label5, idx, 4)
            grid_layout.addWidget(label6, idx, 5)
        return grid_layout

    def create_SysHealthdata_gblayout(self, layout):
        self.clear_layout(layout)  # 调用安全清空函数
        query_result_url = 'https://{ip}:{https_port}/actor/healthCheck/queryCheckResultNoToken'.format(
            ip=self.login_ip, https_port=self.login_https_port)
        result = self.get_queryCheckResult(query_result_url)

        list_checkresult = result['data']['checkResult']
        for item in list_checkresult:
            self.checkTypeDesc = item['checkTypeDesc']
            self.checkType = item['checkType']
            self.checkStatisticDesc = item['checkStatisticDesc']
            # 创建 QGroupBox
            group_box = QGroupBox(self.checkTypeDesc)
            group_layout = QVBoxLayout()
            # 将水平布局添加到主布局
            group_layout.addLayout(self.set_linklayout())
            # 将网格布局(数据展示)设置到 QGroupBox 中
            group_layout.addLayout(self.set_gridlayout(item))
            group_box.setLayout(group_layout)
            # 将 QGroupBox 添加到主布局
            layout.addWidget(group_box)
        return layout

    def create_indexTab(self, tab_title):
        """
        首页
        @param tab_title:标签页名称
        @return:
        """
        tab = QWidget(self)
        # 将标签页添加到 QTabWidget
        self.tabs.addTab(tab, tab_title)

        layout = QVBoxLayout()
        btn_desc_dict = {
            '配置基础数据': '用于配置系统的基础数据，包括厂站，主机，第三方平台，点表，相机等',
            '应用日志': '需要查看应用日志时点击此按钮跳转',
            '重启应用': '需要重启应用时点击此按钮跳转',
            '系统健康状态检查': '配置基础数据后检查系统的各项健康指标',
            '应用状态': '查看所有服务状态',
            '系统更新': '更包时点击此按钮跳转',
        }
        btn_list = list(btn_desc_dict.keys())
        for i in range(0, len(btn_list), 3):
            # 创建水平布局
            hbox = QHBoxLayout()
            for j in range(i, min(i + 3, len(btn_list))):
                # 创建垂直布局来放置按钮和说明文字
                vbox = QVBoxLayout()
                button_text = btn_list[j]
                button = QPushButton(button_text, self)
                button.setFixedSize(500, 50)
                button.clicked.connect(self.slot_index_button_menu)
                vbox.addWidget(button)
                desc_label = QLabel(btn_desc_dict[button_text], self)
                desc_label.setAlignment(Qt.AlignHCenter)  # lable居中
                vbox.addWidget(desc_label)
                vbox.addStretch()  # 空白填充
                hbox.addLayout(vbox)
            layout.addLayout(hbox)
        # 设置中心部件
        tab.setLayout(layout)
        self.tabs.setCurrentWidget(tab)

    def create_appstatusTab(self, tab_title):
        """
        首页
        @param tab_title:标签页名称
        @return:
        """
        tab = QWidget(self)
        # 将标签页添加到 QTabWidget
        self.tabs.addTab(tab, tab_title)
        layout = QVBoxLayout(tab)
        # 在标签页添加控件
        docker_stats_btn = QPushButton('刷新应用状态', self)
        self.appstatus_text = QTextEdit(tab)
        self.appstatus_text.setReadOnly(True)

        # 设置控件
        layout.addWidget(docker_stats_btn)
        layout.addWidget(self.appstatus_text)

        # 控件连接slot
        self.slot_show_containerstatus()  # 首次先获取服务状态
        docker_stats_btn.clicked.connect(self.slot_show_containerstatus)

        # 设置中心部件的布局
        tab.setLayout(layout)
        self.tabs.setCurrentWidget(tab)

    def require_sysversion(self):
        """菜单之前版本检查的装饰器"""
        def decorator(func):
            if comfunc.check_sysversion(self.sysversion):
                return func
        return decorator


    def create_basic_configTab(self, tab_title):
        """
        创建基础配置界面
        :return:
        """
        tab = QWidget(self)
        # 将标签页添加到 QTabWidget
        self.tabs.addTab(tab, tab_title)
        # 创建主体水平布局
        main_layout = QHBoxLayout(tab)

        # 左侧布局
        left_layout = QVBoxLayout()
        left_text_edit = QTextEdit()
        left_text_edit.setReadOnly(True)

        # 插入图片
        image_path = "image/jichu.png"  # 替换为你的图片路径
        image_reader = QImageReader(image_path)
        image = image_reader.read()
        if image.isNull():
            left_text_edit.setPlainText("图片加载失败")
        else:
            # 按比例缩小图片，这里设置缩放比例为 0.5（即缩小为原来的一半）
            scaled_image = image.scaled(int(image.width() * 0.5), int(image.height() * 0.5))
            cursor = QTextCursor(left_text_edit.document())
            cursor.insertBlock()  # 插入一个新段落

            format = QTextBlockFormat()
            format.setAlignment(Qt.AlignHCenter)  # 设置段落水平居中
            cursor.setBlockFormat(format)
            cursor.insertImage(scaled_image)
            left_text_edit.setTextCursor(cursor)
        left_layout.addWidget(left_text_edit)

        # 中间布局
        btn_list = ['导入厂站与执行设备', '导入主机与平台', '导入点表']
        center_layout = QVBoxLayout()
        for j in btn_list:
            button = QPushButton(j, self)
            button.setFixedSize(160, 50)
            center_layout.addWidget(button)
            button.clicked.connect(self.slot_basic_config_click)

        # 右侧布局
        right_layout = QVBoxLayout()
        # 添加说明文本框
        self.bc_text = QTextEdit()
        self.bc_text.setReadOnly(True)
        right_layout.addWidget(self.bc_text)

        # 将三个子布局添加到主水平布局中
        main_layout.addLayout(left_layout)
        main_layout.addLayout(center_layout)
        main_layout.addLayout(right_layout)
        # 将水平布局设置到中心部件上
        tab.setLayout(main_layout)
        self.tabs.setCurrentWidget(tab)

    def create_appLogsTab(self, tab_title):
        """
        服务日志
        @param tab_title:标签页名称
        @return:
        """
        tab = QWidget(self)
        # 将标签页添加到 QTabWidget
        self.tabs.addTab(tab, tab_title)
        layout = QVBoxLayout(tab)

        # 在标签页添加控件
        btn_list = self.get_containers()
        for i in range(0, len(btn_list), 4):
            # 创建水平布局
            hbox = QHBoxLayout()
            for j in range(i, min(i + 4, len(btn_list))):
                button = QPushButton(btn_list[j], self)
                hbox.addWidget(button)
                button.clicked.connect(self.slot_show_dockerlogs)
            layout.addLayout(hbox)
        # 添加解释性文字
        explanation_text = QLabel('单击上方按钮查看对应日志', self)
        explanation_text.setStyleSheet("QLabel { color: red; }")
        explanation_text.setWordWrap(True)  # 开启文字换行
        layout.addWidget(explanation_text)
        # 设置中心部件的布局
        tab.setLayout(layout)
        layout.addStretch()  # 填充空白
        self.tabs.setCurrentWidget(tab)

    def create_rebuildTab(self, tab_title):
        """
        构建服务
        @param tab_title:标签页名称
        @return:
        """
        tab = QWidget(self)
        # 将标签页添加到 QTabWidget
        self.tabs.addTab(tab, tab_title)
        layout = QVBoxLayout(tab)

        # 在标签页添加控件
        rebuildAll_btn = QPushButton('rebuild all', self)
        rebuildAll_btn.clicked.connect(self.slot_show_rebuildlogs)
        layout.addWidget(rebuildAll_btn)

        btn_list = self.get_app_containers()
        for i in range(0, len(btn_list), 4):
            # 创建水平布局
            hbox = QHBoxLayout()
            for j in range(i, min(i + 4, len(btn_list))):
                button = QPushButton(btn_list[j], self)
                hbox.addWidget(button)
                button.clicked.connect(self.slot_show_rebuildlogs)
            layout.addLayout(hbox)
        # 添加解释性文字
        explanation_text = QLabel('单击上方按钮构建对应服务，rebuild all构建全部服务', self)
        explanation_text.setStyleSheet("QLabel { color: red; }")
        explanation_text.setWordWrap(True)  # 开启文字换行
        layout.addWidget(explanation_text)
        self.rebuild_text = QTextEdit(tab)
        self.rebuild_text.setReadOnly(True)

        # 设置控件
        layout.addWidget(self.rebuild_text)

        # 设置中心部件的布局
        tab.setLayout(layout)
        self.tabs.setCurrentWidget(tab)

    def create_restartTab(self, tab_title):
        """
        重启服务
        @param tab_title:标签页名称
        @return:
        """
        tab = QWidget(self)
        # 将标签页添加到 QTabWidget
        self.tabs.addTab(tab, tab_title)
        # 创建主体水平布局
        main_layout = QHBoxLayout(tab)

        # 左侧布局
        left_layout = QVBoxLayout()

        # 在标签页添加控件
        restartAll_btn = QPushButton('restart all', self)
        restartAll_btn.clicked.connect(self.slot_show_restartlogs)
        left_layout.addWidget(restartAll_btn)

        btn_list = self.get_app_containers()
        for i in range(0, len(btn_list), 2):
            # 创建水平布局
            hbox = QHBoxLayout()
            for j in range(i, min(i + 2, len(btn_list))):
                button = QPushButton(btn_list[j], self)
                hbox.addWidget(button)
                button.setFixedSize(300, 50)
                button.clicked.connect(self.slot_show_restartlogs)
            left_layout.addLayout(hbox)
        # 右侧布局
        right_layout = QVBoxLayout()
        # 添加说明文本框
        self.restart_text = QTextEdit()
        self.restart_text.setReadOnly(True)
        right_layout.addWidget(self.restart_text)

        # 将三个子布局添加到主水平布局中
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)

        # 设置中心部件的布局
        tab.setLayout(left_layout)
        self.tabs.setCurrentWidget(tab)

    def create_ServiceTab(self, tab_title):
        """
        重启Linux服务
        @param tab_title:标签页名称
        @return:
        """
        tab = QWidget(self)
        # 将标签页添加到 QTabWidget
        self.tabs.addTab(tab, tab_title)
        layout = QVBoxLayout(tab)

        # 在标签页添加控件
        btn_list = ['xrdp', 'vsftpd', 'docker']
        for i in range(0, len(btn_list), 4):
            # 创建水平布局
            hbox = QHBoxLayout()
            for j in range(i, min(i + 4, len(btn_list))):
                button = QPushButton(btn_list[j], self)
                hbox.addWidget(button)
                button.clicked.connect(self.slot_show_sysService)
            layout.addLayout(hbox)
        # 添加解释性文字
        explanation_text = QLabel('选择上方服务类型进行重启：\n'
                                  '* xrdp：远程桌面服务\n'
                                  '* vsftpd：FTPS服务\n'
                                  '* docker：docker服务', self)
        explanation_text.setStyleSheet("QLabel { color: red; }")
        explanation_text.setWordWrap(True)  # 开启文字换行
        layout.addWidget(explanation_text)
        self.sys_text = QTextEdit(tab)
        self.sys_text.setReadOnly(True)

        # 设置控件
        layout.addWidget(self.sys_text)

        # 设置中心部件的布局
        tab.setLayout(layout)
        self.tabs.setCurrentWidget(tab)

    def create_updatezipTab(self, tab_title):
        """
        上传文件
        @param tab_title:标签页名称
        @return:
        """
        tab = QWidget(self)
        # 将标签页添加到 QTabWidget
        self.tabs.addTab(tab, tab_title)
        # 创建主体水平布局
        main_layout = QHBoxLayout(tab)
        # 左侧布局
        left_layout = QVBoxLayout()
        left_text_edit = QTextEdit()
        left_text_edit.setReadOnly(True)

        # 插入图片
        image_path = "image/shengji.png"  # 替换为你的图片路径
        image_reader = QImageReader(image_path)
        image = image_reader.read()
        if image.isNull():
            left_text_edit.setPlainText("图片加载失败")
        else:
            # 按比例缩小图片，这里设置缩放比例为 0.5（即缩小为原来的一半）
            scaled_image = image.scaled(int(image.width() * 0.5), int(image.height() * 0.5))
            cursor = QTextCursor(left_text_edit.document())
            cursor.insertBlock()  # 插入一个新段落

            format = QTextBlockFormat()
            format.setAlignment(Qt.AlignHCenter)  # 设置段落水平居中
            cursor.setBlockFormat(format)
            cursor.insertImage(scaled_image)
            left_text_edit.setTextCursor(cursor)
        left_layout.addWidget(left_text_edit)

        # 中间布局
        btn_list = ['upgrade', 'jar', 'dist']
        center_layout = QVBoxLayout()
        for j in btn_list:
            button = QPushButton(j, self)
            button.setFixedSize(160, 50)
            center_layout.addWidget(button)
            button.clicked.connect(self.slot_on_updatefile_click)

        # 右侧布局
        right_layout = QVBoxLayout()
        # 载入进度条控件
        self.pgb = QProgressBar()
        right_layout.addWidget(self.pgb)

        # 设置进度条的范围
        self.pgb.setMinimum(0)
        self.pgb.setMaximum(100)
        self.pgb.setValue(0)
        self.zip_text = QTextEdit(tab)
        self.zip_text.setReadOnly(True)
        # 设置控件
        right_layout.addWidget(self.zip_text)

        # 将三个子布局添加到主水平布局中
        main_layout.addLayout(left_layout)
        main_layout.addLayout(center_layout)
        main_layout.addLayout(right_layout)
        # 将水平布局设置到中心部件上
        tab.setLayout(main_layout)
        self.tabs.setCurrentWidget(tab)

    def create_SysHealthTab(self, tab_title):
        """
        系统健康状态
        @param tab_title:标签页名称
        @return:
        """
        tab = QWidget(self)
        # 将标签页添加到 QTabWidget
        self.tabs.addTab(tab, tab_title)
        main_layout = QVBoxLayout(tab)

        # 创建水平布局
        hbox = QHBoxLayout()
        # 创建文字描述标签
        check_text = self.get_checktext()[0]
        self.check_count_label = QLabel(check_text, self)
        hbox.addWidget(self.check_count_label)

        # 创建按钮
        if self.is_checking is False:
            btn_text = "开始"
        else:
            btn_text = "停止"
        self.check_btn = QPushButton(btn_text, self)
        self.check_btn.clicked.connect(self.slot_btn_check)
        hbox.addWidget(self.check_btn)

        # 添加进度条
        self.sht_pgb = QProgressBar()
        # 设置进度条的范围
        self.sht_pgb.setMinimum(0)
        self.sht_pgb.setMaximum(100)
        last_int_check_progress = int(self.get_checktext()[1])
        self.sht_pgb.setValue(last_int_check_progress)
        self.sht_pgb.setFormat("{0:.2f}%".format(self.get_checktext()[1]))

        # 将三个子布局添加到主水平布局中
        main_layout.addLayout(hbox)
        main_layout.addWidget(self.sht_pgb)
        # 创建滚动区域
        self.sysheal_scroll_area = QScrollArea()
        self.sysheal_scroll_area.setWidgetResizable(True)
        # 创建一个用于放置内容的容器并设置容器内布局
        self.sysheal_scroll_widget = QWidget()
        self.sysheal_scroll_layout = QVBoxLayout(self.sysheal_scroll_widget)

        # 调用创建布局的方法
        self.create_SysHealthdata_gblayout(self.sysheal_scroll_layout)
        # 将内容容器设置到滚动区域
        self.sysheal_scroll_area.setWidget(self.sysheal_scroll_widget)
        # 滚动区域添加到主窗口的布局
        main_layout.addWidget(self.sysheal_scroll_area)
        # 设置中心部件的布局
        tab.setLayout(main_layout)
        self.tabs.setCurrentWidget(tab)

    def show_version(self, tab_title):
        """
        版本展示
        @param tab_title:标签页名称
        @return:
        """
        tool_version = 'PyGUI Tool V2.0'
        if tab_title == '系统版本':
            QMessageBox.information(self, '系统版本', self.sysversion)
        elif tab_title == '工具版本':
            QMessageBox.information(self, '工具版本', tool_version)

    def slot_check_isopen(self):
        """
        槽函数，处理菜单与tab页逻辑
        @return:
        """
        # 获取触发动作的文本，即标签页标题
        tab_title = self.sender().text()
        tabs_count = self.tabs.count()
        for i in range(tabs_count):
            if self.tabs.tabText(i) == tab_title:
                self.tabs.setCurrentIndex(i)
                return
        action_menu = {
            '首页': self.create_indexTab,
            '应用日志': self.create_appLogsTab,
            '构建应用': self.create_rebuildTab,
            '重启应用': self.create_restartTab,
            '重启Linux服务': self.create_ServiceTab,
            '系统更新': self.create_updatezipTab,
            '系统版本': self.show_version,
            '工具版本': self.show_version,
        }
        action_menu[tab_title](tab_title)

    def qactionConnectTab(self):
        """
        创建菜单
        @return:
        """
        # 创建菜单栏并关联对应标签页
        app_logsaction_list = self.initMenu('查看', {'首页': None, '应用日志': None, '系统版本': None, '工具版本': None})
        for obj_action in app_logsaction_list:
            obj_action.triggered.connect(self.slot_check_isopen)

        operation_action_list = self.initMenu('操作', {'应用': ['构建应用', '重启应用'], '重启Linux服务': None})
        for obj_action in operation_action_list:
            obj_action.triggered.connect(self.slot_check_isopen)
        update_action_list = self.initMenu('升级', {'系统更新': None})
        update_action_list[0].triggered.connect(self.slot_check_isopen)

    def get_containers(self):
        """
        获取当前运行的容器
        @return:
        """
        container_list = None
        sys_command = 'docker ps --format "{{.Names}}"|xargs'
        com_response, err_response, code_response = self.ssh_instance.execute_ssh_command(sys_command)
        com_text = com_response.read().decode('utf-8')
        err_text = err_response.read().decode('utf-8')
        if err_text:
            QMessageBox.critical(self, '获取容器列表失败', err_text)
            return container_list
        else:
            container_list = com_text.split()
            return container_list

    def get_app_containers(self):
        """
        获取app目录下容器
        @return:
        """
        app_container_list = None
        sys_command = 'grep "container_name:" ~/chiebot-docker-app/docker-deploy/docker-compose.yml |grep -v ^#|cut -d ":" -f 2'
        com_response, err_response, code_response = self.ssh_instance.execute_ssh_command(sys_command)
        com_text = com_response.read().decode('utf-8')
        err_text = err_response.read().decode('utf-8')
        if err_text:
            QMessageBox.critical(self, '获取待构建容器列表失败', err_text)
            return app_container_list
        else:
            app_container_list = com_text.split()
            return app_container_list

    def get_sysInfo(self):
        """
        获取系统信息
        @return:
        """
        patroluser_info = 'patrol:x:1100:1200::/patrol:/bin/bash'
        robotuser_info = 'robot:x:1100:1200::/robot:/bin/bash'
        patrol_command = 'sudo grep {passwdinfo} /etc/passwd'.format(passwdinfo=patroluser_info)
        robot_command = 'sudo grep {passwdinfo} /etc/passwd'.format(passwdinfo=robotuser_info)
        patrol_com_response, patrol_err_response, patrol_code_response = self.ssh_instance.execute_ssh_command(
            patrol_command)
        robot_com_response, robot_err_response, robot_code_response = self.ssh_instance.execute_ssh_command(
            robot_command)
        patrol_com_text = patrol_com_response.read().decode('utf-8')
        patrol_err_text = patrol_err_response.read().decode('utf-8')
        robot_com_text = robot_com_response.read().decode('utf-8')
        robot_err_text = robot_err_response.read().decode('utf-8')
        if patrol_com_text.replace('\n', '') == patroluser_info and robot_com_text.replace('\n', '') == '':
            self.sys_type = '巡视系统'
            get_sysversion_command = "docker exec -i patrol-mysql mysql -pcbs_chiebot1003 -N -e \"SELECT value from patrol.sys_common_setting where type = 'sys_version'\""
            sysversion_com_response, sysversion_err_response, sysversion_code_response = self.ssh_instance.execute_ssh_command(
                get_sysversion_command)
            self.sysversion = sysversion_com_response.read().decode('utf-8')
        elif robot_com_text.replace('\n', '') == robotuser_info and patrol_com_text.replace('\n', '') == '':
            self.sys_type = '机器人系统'
            get_sysversion_command = "docker exec -i robot-mysql mysql -pcbs_chiebot1003 -N -e \"SELECT value from robot.sys_common_setting where type = 'sys_version'\""
            sysversion_com_response, sysversion_err_response, sysversion_code_response = self.ssh_instance.execute_ssh_command(
                get_sysversion_command)
            self.sysversion = sysversion_com_response.read().decode('utf-8')
        else:
            QMessageBox.critical(self, 'Command Error', '校验{ip}系统类型异常：\npatrol_err:{pe} \nAND robot_err:{re}'
                                 .format(ip=self.login_ip, pe=patrol_err_text, re=robot_err_text))
            QMessageBox.critical(self, 'Command Error', '联系开发查看，程序退出！')
            self.close()

    def initUI(self):
        self.set_centralWindow()
        self.initTab()
        self.initStatusbar()
        # 连接错误信号
        signal_bus.error_occurred.connect(self.show_error_message)
        signal_bus.info_occurred.connect(self.show_info_message)

    def show_error_message(self, message):
        """显示错误消息对话框"""
        QMessageBox.critical(self, "错误2", message)

    def show_info_message(self, message):
        """显示普通消息对话框"""
        QMessageBox.information(self, "提示2", message)

    def closeEvent(self, event):
        """
        重写mainwindow的窗口关闭事件，关闭时顺带关闭ssh连接
        @param event:
        @return:
        """
        self.validation_window.showValidation()  # 重新显示验证窗口
        self.hide()
        event.ignore()  # 忽略关闭事件，不关闭应用程序
        self.ssh_instance.close_ssh_connection()


class Login_window(QWidget):
    def __init__(self):
        super().__init__()
        self.get_cbbox()
        self.create_window()

    def save_sshinfo(self):
        """
        以json格式保存ssh登录信息
        @param ssh_ip: 获取的ip,string
        @param ssh_port: 获取的port,string
        @param ssh_user: 获取的user,string
        @param ssh_password: 获取的password,string
        @param https_port: 获取的httpsport,string
        @return:
        """
        # 创建一个字典来存储 SSH 信息
        ssh_info = {
            '系统类型': self.sys_login_type,
            'IP': self.ssh_ip,
            '端口': self.ssh_port,
            '用户名': self.ssh_user,
            '密码': self.ssh_password,
            'HTTPS端口:': self.https_port
        }
        # 将字典写入 JSON 文件
        with open('ssh.key', 'w') as file:
            json.dump(ssh_info, file, indent=4)

    def get_cbbox(self):
        self.combo_box = QComboBox()
        self.combo_box.addItems(["巡视系统", "机器人系统"])
        self.combo_box.currentTextChanged.connect(self.get_selectionchange_text)

    def get_selectionchange_text(self, text):
        if text == "机器人系统":
            # 假设用户名输入框在 self.line_list 中的索引为 2
            self.line_list[2].setText("robot")
            self.line_list[3].setText("cbs_chiebot1003")
            return
        elif text == "巡视系统":
            # 恢复默认用户名和密码
            self.line_list[2].setText("patrol")
            self.line_list[3].setText("cbs_chiebot1003")
            return

    def fbox_withtips(self):
        """
        以表单formlayout布局组装填写的ssh信息
        @return: 组装好的formlayout
        """
        dict_sshinfo = {
            'IP:': '192.168.1.14',
            '端口:': '22',
            '用户名:': 'patrol',
            '密码:': 'cbs_chiebot1003',
            'HTTPS端口:': '443'
        }
        # 使用列表保存qline对象，方便后续取qline输入的值
        self.line_list = []
        # 创建局部表单布局fbox用于放置ssh连接信息
        fbox = QFormLayout()
        for i in dict_sshinfo:
            qline = QLineEdit(self)
            qline.setText(dict_sshinfo[i])
            qline.returnPressed.connect(self.onButtonClick)  # 输入框里按回车触发onButtonClick
            self.line_list.append(qline)
            fbox.addRow(i, qline)
        fbox.insertRow(0, '系统类型', self.combo_box)
        return fbox

    def fbox_withkey(self, file_path):
        """
        以表单formlayout布局组装填写的ssh信息
        @return: 组装好的formlayout
        """
        with open(file_path, 'r') as f:
            dict_sshinfo = json.load(f)

        # 使用列表保存qline对象，方便后续取qline输入的值
        self.line_list = []
        # 创建局部表单布局fbox用于放置ssh连接信息
        fbox = QFormLayout()
        for key, value in dict_sshinfo.items():
            if key == '系统类型':
                pass
            else:
                qline = QLineEdit(self)
                qline.setText(value)
                qline.returnPressed.connect(self.onButtonClick)
                self.line_list.append(qline)
                fbox.addRow(key, qline)
        cb_text = dict_sshinfo['系统类型']
        self.combo_box.setCurrentText(cb_text)
        fbox.insertRow(0, '系统类型', self.combo_box)
        return fbox

    def set_centralWindow(self):
        """
        设置窗口位置跟大小
        @return:
        """
        self.setGeometry(1000, 500, 300, 200)
        # 获取屏幕的几何信息
        screen = QApplication.primaryScreen().geometry()
        # 获取窗口的几何信息
        window_size = self.geometry()
        # 计算窗口居中时的坐标
        x = (screen.width() - window_size.width()) // 2
        y = (screen.height() - window_size.height()) // 2
        # 移动窗口到居中位置
        self.move(x, y)

    def start_ssh_connect(self):
        """
        启动ssh连接
        @return:
        """
        self.save_sshinfo()
        self.file_exec_instance = FileExec(self.ssh_ip, self.ssh_user, self.ssh_password, self.ssh_port)
        self.pyssh_thread = Pyssh(self.ssh_ip, self.ssh_port, self.ssh_user, self.ssh_password)
        self.pyssh_thread.connectionResult.connect(
            self.handle_connection_result)  # 连接 Pyssh 线程的 connectionResult 信号到一个槽，该槽会在线程完成时被调用。
        self.pyssh_thread.start()  # 启动线程进行 SSH 连接

    def check_is_puresys(self):
        """
        检查系统是否符合纯净系统要求
        @return:
        """
        com_response, err_response, code_response = self.pyssh_thread.execute_ssh_command('rpm -qa|grep docker-ce')
        log.logger.info('检测纯净系统命令返回码{status_code}'.format(status_code=code_response))
        if code_response == 0:
            QMessageBox.critical(self, '禁止登录', '检测到{host}为非纯净系统,不予登录！'.format(host=self.ssh_ip))
            return False
        else:
            return True

    def handle_connection_result(self, ssh_response, message):
        """
        处理ssh连接结果
        @param ssh_response:
        @param message:
        @return:
        """
        if ssh_response:
            QMessageBox.information(self, 'SSH Info', message)
            if self.ssh_user == 'patrol' or self.ssh_user == 'robot':
                self.hide()  # 隐藏验证窗口
                self.main_window = Main_window(self, self.ssh_ip, self.ssh_user, self.pyssh_thread,
                                               self.file_exec_instance, self.https_port)  # 创建主界面实例
                self.main_window.show()  # 显示主界面
            elif self.ssh_user == 'root' and self.check_is_puresys():
                self.hide()  # 隐藏验证窗口
                self.deploy_window = Deploy_window(self, self.sys_login_type, self.ssh_ip, self.ssh_user,
                                                   self.pyssh_thread, self.file_exec_instance)  # 创建主界面实例
                self.deploy_window.show()  # 显示主界面
        else:
            QMessageBox.critical(self, 'SSH Connection Error', message)
        self.con_btn.setText("点击连接")
        self.con_btn.setEnabled(True)  # 重新启用按钮

    def get_sshinfo(self):
        """
        获取ssh信息
        @return:
        """
        self.sys_login_type = self.combo_box.currentText()
        sshinfo_obj_list = self.line_list
        self.ssh_ip = sshinfo_obj_list[0].text()
        self.ssh_port = sshinfo_obj_list[1].text()
        self.ssh_user = sshinfo_obj_list[2].text()
        self.ssh_password = sshinfo_obj_list[3].text()
        self.https_port = sshinfo_obj_list[4].text()

    def onButtonClick(self):
        """
        定义'点击连接'按钮执行动作
        @return:
        """
        log.logger.info('点击了登录按钮onButtonClick')
        self.con_btn.setText("连接中,等待响应...")
        self.con_btn.setEnabled(False)  # 禁用按钮以防止重复点击
        self.get_sshinfo()
        if comfunc.validate_ip(self.ssh_ip) and comfunc.validate_port(self.ssh_port):
            if comfunc.validate_sshuser(self.ssh_user):
                log.logger.info("ssh信息校验通过")
                self.start_ssh_connect()
            else:
                QMessageBox.warning(self, '登录验证失败', '用户名只允许patrol,robot,root')
                log.logger.error('登录验证失败,用户名只允许patrol,robot,root')
                self.con_btn.setText("点击连接")
                self.con_btn.setEnabled(True)  # 重新启用按钮
        else:
            QMessageBox.warning(self, '登录验证失败', 'IP 地址或端口无效')
            log.logger.error('登录验证失败,IP 地址或端口无效')
            self.con_btn.setText("点击连接")
            self.con_btn.setEnabled(True)  # 重新启用按钮

    def create_window(self):
        """
        创建登录窗口，以垂直布局为主体布局
        @return:
        """
        # 创建窗口
        self.setWindowTitle('新建连接')
        self.set_centralWindow()
        # 设置窗口图标，确保替换为你的图标文件路径
        self.setWindowIcon(QIcon('icon/new_session.png'))

        # 创建主体垂直布局vbox
        vbox = QVBoxLayout()
        try:
            file_path = 'ssh.key'
            if os.path.exists(file_path):
                ssh_layout = self.fbox_withkey(file_path)
            else:
                ssh_layout = self.fbox_withtips()
        except Exception as e:
            # 捕获任何异常并打印错误信息
            print(f"An error occurred: {e}")
            ssh_layout = self.fbox_withtips()

        vbox.addLayout(ssh_layout)
        self.con_btn = QPushButton("点击连接")
        self.con_btn.setFixedSize(200, 30)
        vbox.addWidget(self.con_btn, alignment=Qt.AlignRight)
        self.con_btn.clicked.connect(self.onButtonClick)
        self.setLayout(vbox)  # 设置类对象（QWidget）使用vbox作为窗口整体布局管理

    def showValidation(self):
        self.show()  # 重新显示验证窗口


if __name__ == '__main__':
    app = QApplication(sys.argv)
    lw = Login_window()
    lw.show()
    sys.exit(app.exec_())
