import json
import os
import sys
import warnings
import datetime
from appLog import Logger

from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import QPushButton, QLineEdit, QWidget, QVBoxLayout, QApplication, QFormLayout, \
     QTextEdit, QMessageBox, QMainWindow, QAction, QTabWidget, QHBoxLayout, QLabel, QFileDialog, QDialog, QProgressBar
from Pyssh import Pyssh, CommandThread, FileExec



warnings.filterwarnings("ignore", category=DeprecationWarning)

log = Logger('app.log', level='debug')


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


class Main_window(QMainWindow):
    def __init__(self, validation_window, ssh_ip, ssh_user, ssh_thread, file_exec_instance):
        """

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
        self.last_clicked_button = None
        self.logwindows = {}
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
        # 创建一个QTimer对象
        # self.interval_time = QTimer(self)
        # 给QTimer设定一个时间，每到达这个时间一次就会调用一次该方法
        # self.interval_time.timeout.connect(self.auto_click)

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
        status_message = '已登录主机:{ip} 登录账号:{user}  系统类型:{sys_type}'\
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
        com_response, err_response = self.ssh_instance.execute_ssh_command(sys_command)
        com_text = com_response.read().decode('utf-8')
        err_text = err_response.read().decode('utf-8')
        if err_text:
            QMessageBox.critical(self, 'Command Error', err_text)
            self.index_text.setPlainText(com_text)
        else:
            self.index_text.setPlainText(com_text)

    def slot_show_dockerlogs(self):
        """
        槽函数，展示容器日志
        @return:
        """
        # self.last_clicked_button = self.sender()
        btn_name = self.sender().text()
        if self.logwindows.get(btn_name):
            self.logwindows[btn_name].show()
            self.logwindows[btn_name].activateWindow()
        else:
            new_win = NewWindow(btn_name, self)
            new_win.show()
            ssh_command = 'docker logs -f --tail 100 {containername}'.format(containername=btn_name)
            self.command_thread = CommandThread(self.ssh_instance.ssh_client, ssh_command)
            self.command_thread.commandResult.connect(new_win.append_text)
            self.command_thread.start()
            self.logwindows[btn_name] = new_win

    # def start_showlogs(self):
        # 设置QTimer开始计时，且设定时间为1000ms
        # self.interval_time.start(1000)
        # log.logger.info('开启自动刷新')

    # def stop_showlogs(self):
        # self.interval_time.stop()
        # log.logger.info('关闭自动刷新')

    # def auto_click(self):
        # if self.last_clicked_button is None:
        #     QMessageBox.critical(self, '使用提示', '先点击上方任意查看日志按钮再开启自动刷新')
        #     self.stop_showlogs()
        # else:
        #     self.last_clicked_button.click()

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
            com_response, err_response = self.ssh_instance.execute_ssh_command(sys_command)
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

            com_response, err_response = self.ssh_instance.execute_ssh_command(sys_command)
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

            com_response, err_response = self.ssh_instance.execute_ssh_command(sys_command)
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
            print('total异常%s'%total)

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
                self.start_upload_file(local_path=local_path,remote_path=remote_path)
                self.ssh_instance.execute_ssh_command('docker restart {svc}'.format(svc=svc_name))
                self.zip_text.append('重启服务：{svc}'.format(svc=svc_name))
            else:
                log.logger.info('取消选择文件{file}'.format(file=filename))
        else:
            log.logger.info('点击了按钮[jar],未选择文件')

    def handel_distfile(self):
        """
        处理dist包逻辑
        @return:
        """
        get_filename_path, _ = QFileDialog.getOpenFileName(self, caption="选择文件", directory=self.desktop_path,
                                                       filter="Zip Files (*.zip)")
        filename = os.path.basename(get_filename_path)      # dist.zip
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
                    # 单线程方法
                    # com_response,err_response = self.ssh_instance.execute_ssh_command('docker stop patrol-ui && cd ~/chiebot-docker-app/frontend/ \
                    #     && mv dist dist.bak_{bakdate} && unzip {dist} && docker start patrol-ui'.format(bakdate=now, dist=filename))
                    # com_text = com_response.read().decode('utf-8')
                    # err_text = err_response.read().decode('utf-8')
                    # if err_text:
                    #     self.zip_text.append(err_text)
                    # else:
                    #     self.zip_text.append(com_text)
                    #     self.zip_text.append('启动服务：patrol-ui')
                else:
                    log.logger.info('取消选择文件{file}'.format(file=filename))
            else:
                QMessageBox.critical(self, 'File Type Error', '文件名有误！只接受dist.zip')
        else:
            log.logger.info('点击了按钮[dist],未选择文件')

    def handel_zipfile(self):
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
                    com_response, err_response = self.ssh_instance.execute_ssh_command('ls /{login_user}/{shfile}'
                                                            .format(login_user=self.login_user, shfile=shfile))
                    com_text = com_response.read().decode('utf-8')
                    err_text = err_response.read().decode('utf-8')
                    if err_text:
                        self.zip_text.append(err_text)
                        QMessageBox.critical(self, 'File Not Exit', '执行文件{shfile}在{ip}上未找到，上传{shfile}后重试!'
                                             .format(shfile=shfile, ip=self.login_ip))
                    elif com_text.replace('\n', '') == '/{login_user}/{shfile}'.format(login_user=self.login_user, shfile=shfile):
                        self.zip_text.append(com_text)
                        self.start_upload_file(local_path=local_path, remote_path=remote_path)
                        # 多线程方法
                        ssh_command = 'bash /{login_user}/{shfile}'.format(login_user=self.login_user, shfile=shfile)
                        self.command_thread = CommandThread(self.ssh_instance.ssh_client, ssh_command)
                        self.command_thread.commandResult.connect(lambda text: self.zip_text.append(text))
                        self.command_thread.start()
                    #     单线程方法
                    #     bash_com_response, bash_err_response = self.ssh_instance.execute_ssh_command('bash /{login_user}/{shfile}'
                    #                                         .format(login_user=self.login_user, shfile=shfile))
                    #     bash_com_text = bash_com_response.read().decode('utf-8')
                    #     bash_err_text = bash_err_response.read().decode('utf-8')
                    #     self.zip_text.append(bash_com_text)
                    # else:
                    #     self.zip_text.append(com_text)
                else:
                    log.logger.info('取消选择文件{file}'.format(file=filename))
            else:
                QMessageBox.critical(self, 'File Type Error', '文件名有误！只接受upgrade.zip')
        else:
            log.logger.info('点击了按钮[upgrade],未选择文件')

    def slot_on_updatefie_click(self):
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
            self.handel_distfile()
        elif btn_name == 'upgrade':
            self.handel_zipfile()
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

    def create_indexTab(self, tab_title):
        """
        首页
        @param tab_title:
        @return:
        """
        tab = QWidget(self)
        # 将标签页添加到 QTabWidget
        self.tabs.addTab(tab, tab_title)
        layout = QVBoxLayout(tab)
        # 在标签页添加控件
        docker_stats_btn = QPushButton('刷新应用状态', self)
        self.index_text = QTextEdit(tab)
        self.index_text.setReadOnly(True)

        # 设置控件
        layout.addWidget(docker_stats_btn)
        layout.addWidget(self.index_text)

        # 控件连接slot
        self.slot_show_containerstatus()  # 首次先获取服务状态
        docker_stats_btn.clicked.connect(self.slot_show_containerstatus)

        # 设置中心部件的布局
        tab.setLayout(layout)
        self.tabs.setCurrentWidget(tab)

    def create_appLogsTab(self, tab_title):
        """
        服务日志
        @param tab_title:
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
        @param tab_title:
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
        @param tab_title:
        @return:
        """
        tab = QWidget(self)
        # 将标签页添加到 QTabWidget
        self.tabs.addTab(tab, tab_title)
        layout = QVBoxLayout(tab)

        # 在标签页添加控件
        restartAll_btn = QPushButton('restart all', self)
        restartAll_btn.clicked.connect(self.slot_show_restartlogs)
        layout.addWidget(restartAll_btn)

        btn_list = self.get_app_containers()
        for i in range(0, len(btn_list), 4):
            # 创建水平布局
            hbox = QHBoxLayout()
            for j in range(i, min(i + 4, len(btn_list))):
                button = QPushButton(btn_list[j], self)
                hbox.addWidget(button)
                button.clicked.connect(self.slot_show_restartlogs)
            layout.addLayout(hbox)
        # 添加解释性文字
        explanation_text = QLabel('单击上方按钮重启对应服务，restart all重启全部服务', self)
        explanation_text.setStyleSheet("QLabel { color: #0087FF; }")
        explanation_text.setWordWrap(True)  # 开启文字换行
        layout.addWidget(explanation_text)
        self.restart_text = QTextEdit(tab)
        self.restart_text.setReadOnly(True)

        # 设置控件
        layout.addWidget(self.restart_text)

        # 设置中心部件的布局
        tab.setLayout(layout)
        self.tabs.setCurrentWidget(tab)


    def create_ServiceTab(self, tab_title):
        """
        重启Linux服务
        @param tab_title:
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
        @param tab_title:
        @return:
        """
        tab = QWidget(self)
        # 将标签页添加到 QTabWidget
        self.tabs.addTab(tab, tab_title)
        layout = QVBoxLayout(tab)
        # 在标签页添加控件
        btn_list = ['upgrade', 'jar', 'dist']
        for i in range(0, len(btn_list), 4):
            # 创建水平布局
            hbox = QHBoxLayout()
            for j in range(i, min(i + 4, len(btn_list))):
                button = QPushButton(btn_list[j], self)
                hbox.addWidget(button)
                button.clicked.connect(self.slot_on_updatefie_click)
            layout.addLayout(hbox)
            # 添加解释性文字
            explanation_text = QLabel('选择上方文件类型进行更新：\n'
                                      '* upgrade：目前只接受upgrade.zip\n'
                                      '* jar：更新jar包时使用，如patrol-task.jar,robot-system.jar\n'
                                      '* dist：更新dist包时使用，只接受dist.zip', self)
            explanation_text.setStyleSheet("QLabel { color: red; }")
            explanation_text.setWordWrap(True)  # 开启文字换行
            layout.addWidget(explanation_text)
            # 载入进度条控件
            self.pgb = QProgressBar(self)
            layout.addWidget(self.pgb)

            # 设置进度条的范围
            self.pgb.setMinimum(0)
            self.pgb.setMaximum(100)
            self.pgb.setValue(0)
            self.zip_text = QTextEdit(tab)
            self.zip_text.setReadOnly(True)

            # 设置控件
            layout.addWidget(self.zip_text)

        # 设置中心部件的布局
        tab.setLayout(layout)
        self.tabs.setCurrentWidget(tab)

    def show_version(self, tab_title):
        """
        版本展示
        @param tab_title:
        @return:
        """
        tool_version = 'PyGUI Tool V1.0'
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
            '上传文件': self.create_updatezipTab,
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
        update_action_list = self.initMenu('升级', {'上传文件': None})
        update_action_list[0].triggered.connect(self.slot_check_isopen)

    def get_containers(self):
        """
        获取当前运行的容器
        @return:
        """
        container_list = None
        sys_command = 'docker ps --format "{{.Names}}"|xargs'
        com_response, err_response = self.ssh_instance.execute_ssh_command(sys_command)
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
        com_response, err_response = self.ssh_instance.execute_ssh_command(sys_command)
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
        patrol_com_response, patrol_err_response = self.ssh_instance.execute_ssh_command(patrol_command)
        robot_com_response, robot_err_response = self.ssh_instance.execute_ssh_command(robot_command)
        patrol_com_text = patrol_com_response.read().decode('utf-8')
        patrol_err_text  = patrol_err_response.read().decode('utf-8')
        robot_com_text = robot_com_response.read().decode('utf-8')
        robot_err_text = robot_err_response.read().decode('utf-8')
        print('a={a},b={b},c={c},d={d}'.format(a=patrol_com_text,b=patrol_err_text,c=robot_com_text,d=robot_err_text))
        if patrol_com_text.replace('\n', '') == patroluser_info and robot_com_text.replace('\n', '') == '':
            self.sys_type = '巡视系统'
            get_sysversion_command = "docker exec -i patrol-mysql mysql -pcbs_chiebot1003 -N -e \"SELECT value from patrol.sys_common_setting where type = 'sys_version'\""
            sysversion_com_response, sysversion_err_response = self.ssh_instance.execute_ssh_command(get_sysversion_command)
            self.sysversion = sysversion_com_response.read().decode('utf-8')
        elif robot_com_text.replace('\n', '') == robotuser_info and patrol_com_text.replace('\n', '') == '':
            self.sys_type = '机器人系统'
            get_sysversion_command = "docker exec -i robot-mysql mysql -pcbs_chiebot1003 -N -e \"SELECT value from robot.sys_common_setting where type = 'sys_version'\""
            sysversion_com_response, sysversion_err_response = self.ssh_instance.execute_ssh_command(get_sysversion_command)
            self.sysversion = sysversion_com_response.read().decode('utf-8')
        else:
            QMessageBox.critical(self, 'Command Error', '校验{ip}系统类型异常：\npatrol_err:{pe} \nAND robot_err:{re}'
                                 .format(ip=self.login_ip,pe=patrol_err_text, re=robot_err_text))
            QMessageBox.critical(self, 'Command Error', '联系开发查看，程序退出！')
            self.close()

    def initUI(self):
        self.set_centralWindow()
        self.initTab()
        self.initStatusbar()

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
        self.create_window()

    def validate_ip(self, ip):
        """
        简单的 IP 地址验证
        @param ip:
        @return:
        """
        parts = ip.split('.')
        return len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)

    def validate_port(self, port):
        """
        简单的端口验证
        @param port:
        @return:
        """
        try:
            port_int = int(port)
            return 0 <= port_int <= 65535
        except ValueError:
            return False

    def validate_sshuser(self, sshuser):
        """
        简单的用户筛选
        @param sshuser: 输入的用户名
        @return:
        """
        allowed_user = ['patrol', 'robot']
        if sshuser in allowed_user:
            return True
        else:
            return False

    def save_sshinfo(self):
        """
        以json格式保存ssh登录信息
        @param ssh_ip: 获取的ip,string
        @param ssh_port: 获取的port,string
        @param ssh_user: 获取的user,string
        @param ssh_password: 获取的password,string
        @return:
        """
        # 创建一个字典来存储 SSH 信息
        ssh_info = {
            'IP': self.ssh_ip,
            '端口': self.ssh_port,
            '用户名': self.ssh_user,
            '密码': self.ssh_password
        }
        # 将字典写入 JSON 文件
        with open('ssh.key', 'w') as file:
            json.dump(ssh_info, file, indent=4)

    def fbox_withtips(self):
        """
        以表单formlayout布局组装填写的ssh信息
        @return: 组装好的formlayout
        """
        dict_sshinfo = {
            'IP:': '输入主机IP,例如:192.168.1.14',
            '端口:': '输入主机SSH端口,例如:22',
            '用户名:': '巡视主机:patrol，机器人主机:robot',
            '密码:': '输入主机密码,例如:cbs_chiebot1003',
        }

        # 使用列表保存qline对象，方便后续取qline输入的值
        self.line_list = []
        # 创建局部表单布局fbox用于放置ssh连接信息
        fbox = QFormLayout()
        for i in dict_sshinfo:
            qline = QLineEdit(self)
            qline.setPlaceholderText(dict_sshinfo[i])
            qline.returnPressed.connect(self.onButtonClick)  # 输入框里按回车触发onButtonClick
            self.line_list.append(qline)
            fbox.addRow(i, qline)
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
        for i in dict_sshinfo:
            qline = QLineEdit(self)
            qline.setText(dict_sshinfo[i])
            qline.returnPressed.connect(self.onButtonClick)  # 输入框里按回车触发onButtonClick
            self.line_list.append(qline)
            fbox.addRow(i, qline)
        return fbox

    def set_centralWindow(self):
        """
        设置窗口位置跟大小
        @return:
        """
        self.setGeometry(1000, 500, 400, 200)
        screen = QApplication.desktop().screenGeometry()
        window_size = self.geometry()
        x = (screen.width() - window_size.width()) // 2
        y = (screen.height() - window_size.height()) // 2
        self.move(x, y)

    def start_ssh_connect(self):
        """
        启动ssh连接
        @return:
        """
        self.save_sshinfo()
        self.file_exec_instance = FileExec(self.ssh_ip, self.ssh_user, self.ssh_password, self.ssh_port)
        self.pyssh_thread = Pyssh(self.ssh_ip, self.ssh_port, self.ssh_user, self.ssh_password)
        self.pyssh_thread.connectionResult.connect(self.handle_connection_result)  # 连接 Pyssh 线程的 connectionResult 信号到一个槽，该槽会在线程完成时被调用。
        self.pyssh_thread.start()  # 启动线程进行 SSH 连接

    def handle_connection_result(self, ssh_response, message):
        """
        处理ssh连接结果
        @param ssh_response:
        @param message:
        @return:
        """
        if ssh_response:
            QMessageBox.information(self, 'SSH Info', message)
            self.hide()  # 隐藏验证窗口
            self.main_window = Main_window(self, self.ssh_ip, self.ssh_user, self.pyssh_thread, self.file_exec_instance)  # 创建主界面实例
            self.main_window.show()  # 显示主界面
            log.logger.info('已登录主界面')
        else:
            QMessageBox.critical(self, 'SSH Connection Error', message)
        self.con_btn.setText("点击连接")
        self.con_btn.setEnabled(True)  # 重新启用按钮

    def get_sshinfo(self):
        """
        获取ssh信息
        @return:
        """
        sshinfo_obj_list = self.line_list
        self.ssh_ip = sshinfo_obj_list[0].text()
        self.ssh_port = sshinfo_obj_list[1].text()
        self.ssh_user = sshinfo_obj_list[2].text()
        self.ssh_password = sshinfo_obj_list[3].text()

    def onButtonClick(self):
        """
        定义'点击连接'按钮执行动作
        @return:
        """
        log.logger.info('点击了登录按钮onButtonClick')
        self.con_btn.setText("连接中,等待响应...")
        self.con_btn.setEnabled(False)  # 禁用按钮以防止重复点击
        self.get_sshinfo()
        if self.validate_ip(self.ssh_ip) and self.validate_port(self.ssh_port):
            if self.validate_sshuser(self.ssh_user):
                log.logger.info("ssh信息校验通过")
                self.start_ssh_connect()
            else:
                QMessageBox.warning(self, '登录验证失败', '用户名只允许patrol或robot')
                log.logger.error('登录验证失败,用户名只允许patrol或robot')
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
