# coding:utf-8

import sys
import io
import os
import time
import re

sys.path.append(os.getcwd() + "/class/core")
import mw

app_debug = False
if mw.isAppleSystem():
    app_debug = True


def getPluginName():
    return 'zabbix'


def getPluginDir():
    return mw.getPluginDir() + '/' + getPluginName()


def getServerDir():
    return mw.getServerDir() + '/' + getPluginName()


def getInitDFile():
    current_os = mw.getOs()
    if current_os == 'darwin':
        return '/tmp/' + getPluginName()

    if current_os.startswith('freebsd'):
        return '/etc/rc.d/' + getPluginName()

    return '/etc/init.d/' + getPluginName()


def getConf():
    path = getServerDir() + "/redis.conf"
    return path


def getConfTpl():
    path = getPluginDir() + "/config/redis.conf"
    return path


def getInitDTpl():
    path = getPluginDir() + "/init.d/" + getPluginName() + ".tpl"
    return path


def getArgs():
    args = sys.argv[3:]
    tmp = {}
    args_len = len(args)

    if args_len == 1:
        t = args[0].strip('{').strip('}')
        if t.strip() == '':
            tmp = []
        else:
            t = t.split(':')
            tmp[t[0]] = t[1]
        tmp[t[0]] = t[1]
    elif args_len > 1:
        for i in range(len(args)):
            t = args[i].split(':')
            tmp[t[0]] = t[1]
    return tmp

def checkArgs(data, ck=[]):
    for i in range(len(ck)):
        if not ck[i] in data:
            return (False, mw.returnJson(False, '参数:(' + ck[i] + ')没有!'))
    return (True, mw.returnJson(True, 'ok'))

def configTpl():
    path = getPluginDir() + '/tpl'
    pathFile = os.listdir(path)
    tmp = []
    for one in pathFile:
        file = path + '/' + one
        tmp.append(file)
    return mw.getJson(tmp)


def readConfigTpl():
    args = getArgs()
    data = checkArgs(args, ['file'])
    if not data[0]:
        return data[1]

    content = mw.readFile(args['file'])
    content = contentReplace(content)
    return mw.returnJson(True, 'ok', content)

def getPidFile():
    file = getConf()
    content = mw.readFile(file)
    rep = 'pidfile\s*(.*)'
    tmp = re.search(rep, content)
    return tmp.groups()[0].strip()

def status():
    cmd = "ps aux|grep zabbix-server |grep -v grep | grep -v python | grep -v mdserver-web | awk '{print $2}'"
    data = mw.execShell(cmd)
    if data[0] == '':
        return 'stop'
    return 'start'

def contentReplace(content):
    service_path = mw.getServerDir()
    content = content.replace('{$ROOT_PATH}', mw.getRootDir())
    content = content.replace('{$SERVER_PATH}', service_path)
    content = content.replace('{$ZABBIX_ROOT}', '/usr/share/zabbix')
    content = content.replace('{$ZABBIX_PORT}', '18888')
    return content


def initDreplace():
    nginx_src_tpl = getPluginDir()+'/conf/zabbix.nginx.conf'
    nginx_dst_tpl = mw.getServerDir()+'/web_conf/nginx/vhost/zabbix.conf'

    if not os.path.exists(nginx_dst_tpl):
        content = mw.readFile(nginx_src_tpl)
        content = contentReplace(content)
        mw.writeFile(nginx_dst_tpl, content)

    # zcat /usr/share/zabbix-sql-scripts/mysql/server.sql.gz | /www/server/mysql/bin/mysql --default-character-set=utf8mb4 -uzabbix -p"4sPhWWwL7zcDyLX5" zabbix

    # service zabbix-server start
    return True


def zOp(method):

    initDreplace()

    current_os = mw.getOs()
    if current_os.startswith("freebsd"):
        data = mw.execShell('service ' + getPluginName() + ' ' + method)
        if data[1] == '':
            return 'ok'
        return data[1]

    data = mw.execShell('systemctl ' + method + ' ' + getPluginName())
    if data[1] == '':
        return 'ok'
    return data[1]


def start():
    return zOp('start')


def stop():
    return zOp('stop')


def restart():
    status = zOp('restart')

    log_file = runLog()
    mw.execShell("echo '' > " + log_file)
    return status


def reload():
    return zOp('reload')


def getPort():
    conf = getServerDir() + '/redis.conf'
    content = mw.readFile(conf)

    rep = "^(" + 'port' + ')\s*([.0-9A-Za-z_& ~]+)'
    tmp = re.search(rep, content, re.M)
    if tmp:
        return tmp.groups()[1]

    return '6379'


def getRedisCmd():
    requirepass = ""
    conf = getServerDir() + '/redis.conf'
    content = mw.readFile(conf)
    rep = "^(requirepass" + ')\s*([.0-9A-Za-z_& ~]+)'
    tmp = re.search(rep, content, re.M)
    if tmp:
        requirepass = tmp.groups()[1]

    default_ip = '127.0.0.1'
    port = getPort()
    # findDebian = mw.execShell('cat /etc/issue |grep Debian')
    # if findDebian[0] != '':
    #     default_ip = mw.getLocalIp()
    cmd = getServerDir() + "/bin/redis-cli -h " + \
        default_ip + ' -p ' + port + " "

    if requirepass != "":
        cmd = getServerDir() + '/bin/redis-cli -h ' + default_ip + \
            ' -p ' + port + ' -a "' + requirepass + '" '

    return cmd


def initdStatus():
    current_os = mw.getOs()
    if current_os == 'darwin':
        return "Apple Computer does not support"

    if current_os.startswith('freebsd'):
        initd_bin = getInitDFile()
        if os.path.exists(initd_bin):
            return 'ok'

    shell_cmd = 'systemctl status ' + \
        getPluginName() + ' | grep loaded | grep "enabled;"'
    data = mw.execShell(shell_cmd)
    if data[0] == '':
        return 'fail'
    return 'ok'


def initdInstall():
    current_os = mw.getOs()
    if current_os == 'darwin':
        return "Apple Computer does not support"

    # freebsd initd install
    if current_os.startswith('freebsd'):
        import shutil
        source_bin = initDreplace()
        initd_bin = getInitDFile()
        shutil.copyfile(source_bin, initd_bin)
        mw.execShell('chmod +x ' + initd_bin)
        mw.execShell('sysrc ' + getPluginName() + '_enable="YES"')
        return 'ok'

    mw.execShell('systemctl enable ' + getPluginName())
    return 'ok'


def initdUinstall():
    current_os = mw.getOs()
    if current_os == 'darwin':
        return "Apple Computer does not support"

    if current_os.startswith('freebsd'):
        initd_bin = getInitDFile()
        os.remove(initd_bin)
        mw.execShell('sysrc ' + getPluginName() + '_enable="NO"')
        return 'ok'

    mw.execShell('systemctl disable ' + getPluginName())
    return 'ok'


def runLog():
    return getServerDir() + '/data/redis.log'


def getRedisConfInfo():
    conf = getServerDir() + '/redis.conf'

    gets = [
        {'name': 'bind', 'type': 2, 'ps': '绑定IP(修改绑定IP可能会存在安全隐患)','must_show':1},
        {'name': 'port', 'type': 2, 'ps': '绑定端口','must_show':1},
        {'name': 'timeout', 'type': 2, 'ps': '空闲链接超时时间,0表示不断开','must_show':1},
        {'name': 'maxclients', 'type': 2, 'ps': '最大连接数','must_show':1},
        {'name': 'databases', 'type': 2, 'ps': '数据库数量','must_show':1},
        {'name': 'requirepass', 'type': 2, 'ps': 'redis密码,留空代表没有设置密码','must_show':1},
        {'name': 'maxmemory', 'type': 2, 'ps': 'MB,最大使用内存,0表示不限制','must_show':1},
        {'name': 'slaveof', 'type': 2, 'ps': '同步主库地址','must_show':0},
        {'name': 'masterauth', 'type': 2, 'ps': '同步主库密码', 'must_show':0}
    ]
    content = mw.readFile(conf)

    result = []
    for g in gets:
        rep = "^(" + g['name'] + ')\s*([.0-9A-Za-z_& ~]+)'
        tmp = re.search(rep, content, re.M)
        if not tmp:
            if g['must_show'] == 0:
                continue

            g['value'] = ''
            result.append(g)
            continue
        g['value'] = tmp.groups()[1]
        if g['name'] == 'maxmemory':
            g['value'] = g['value'].strip("mb")
        result.append(g)

    return result


if __name__ == "__main__":
    func = sys.argv[1]
    if func == 'status':
        print(status())
    elif func == 'start':
        print(start())
    elif func == 'stop':
        print(stop())
    elif func == 'restart':
        print(restart())
    elif func == 'reload':
        print(reload())
    elif func == 'initd_status':
        print(initdStatus())
    elif func == 'initd_install':
        print(initdInstall())
    elif func == 'initd_uninstall':
        print(initdUinstall())
    elif func == 'conf':
        print(getConf())
    elif func == 'run_log':
        print(runLog())
    elif func == 'config_tpl':
        print(configTpl())
    else:
        print('error')
