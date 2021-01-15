# -*- encoding: utf-8 -*-
'''
@File    :   onekey_log.py
@Time    :   2021/01/15 15:48:29
@Author  :   hongchunhua
@Contact :   hongchunhua@ruijie.com.cn
@License :   (C)Copyright 2020-2025
'''
import paramiko
import os
import sys, getopt
import re
import time, datetime

#一键收集zk日志
def collect_zkdatalog(param, trans):
   ssh = paramiko.SSHClient()
   ssh._transport = trans

   now = datetime.datetime.now()
   log_time = now.strftime("%Y-%m-%d-%H-%M-%S")
   log_name = 'zk-datalog_'+ param['addr'] + '_'+log_time
   file_name = log_name+".tar.gz"
   log_root_path='/var/log/zk_log_tmp_'+log_time

   print("start collect zk datalog and package in remote path[%s]..." %(log_root_path))
   try:
      cmd = "mkdir {path};".format(path=log_root_path)
      ssh.exec_command(cmd)
      cmd ="ls /opt/zookeeper/datalog/version-2/log.*;"
      zk_log_export_cmd = '/opt/java/zookeeper/bin/zkTxnLogToolkit.sh'

      stdin, stdout, stderr = ssh.exec_command(cmd)
      log_list = stdout.read().decode()
      log_list = log_list.split('\n')
      #log_list.sort()
      log_list.reverse()

      i = 0
      for value in log_list:
         patter = re.match('/opt/zookeeper/datalog/version-2', value)
         if patter is None:
            continue
         cmd = zk_log_export_cmd + ' ' + value + ' > ' + log_root_path + '/' + value
         cmd = "{zk_cmd} {log_file} > {log_path}/{log_name}".format(zk_cmd=zk_log_export_cmd, log_file=value, log_path = log_root_path, log_name=str(i) + '.log')
         print(cmd)
         ssh.exec_command(cmd)
         i = i + 1
         # 默认只收集最新的日志
         if i >= param['zknum']:
            break
      
      time.sleep(1)
      cmd ="tar -zcf {path}/{name} ./ -C {path};".format(name=file_name, path=log_root_path)
      ssh.exec_command(cmd)

      time.sleep(1)

      # 实例化一个 sftp对象,指定连接的通道
      sftp = paramiko.SFTPClient.from_transport(trans)

      print("start download datalog file[%s]..." %(file_name))
      # 下载文件
      sftp.get("{path}/{name}".format(name=file_name, path=log_root_path), os.path.join(os.getcwd(),file_name))
      print("download success! file path[%s]!" %(os.path.join(os.getcwd(),file_name)))
   except IOError as err:
      print("download fail! err:[%s]!" %(err))
      raise
   except Exception as err:
      raise
   finally:
      print("clean log path[%s] on remote ..." %(log_root_path))
      #rm -rf 操作要慎重
      if re.match("/var/log/zk_log_tmp", log_root_path):
         cmd = "rm -rf " + log_root_path
         ssh.exec_command(cmd)
      else:
         print('invalid path[%s] to rm -rf, it is dangerous!!!!' %(log_root_path))
         raise "invalid path:"+log_root_path


# 一键收集日志
def collect_log(param, trans):
   ssh = paramiko.SSHClient()
   ssh._transport = trans

   now = datetime.datetime.now()
   log_time = now.strftime("%Y-%m-%d-%H-%M-%S")
   log_name = 'pos-log_'+ param['addr'] + '_'+log_time
   file_name = log_name+".tar.gz"
   log_root_path='/var/log/pos_log_tmp_'+log_time

   print("start collect pos log and package in path[%s]..." %(log_root_path))
   try:
      cmd = "mkdir {path};".format(path=log_root_path)
      cmd +="cd {path};".format(path=log_root_path)
      cmd += ("mkdir {journal,zk_log,pdeployer,papiserver,pos};"
            "journalctl -r -n 5000 > journal/journal_log.log;"
            "cp /var/log/zookeeper/*.log zk_log/;"
            "cp /var/log/rcos/pdeployer/*.log pdeployer/;"
            "cp /var/log/rcos/pos/*.log pos/;"
            "cp /var/log/rcos/pos/*.xz pos/;"
            "cp /var/log/system_track/user_operate_audit.log .;"
            "cp /var/log/rcos/pos/papiserver/* papiserver/;")
      cmd +="tar -zcf {path}/{name} ./ -C {path};".format(name=file_name, path=log_root_path)
      ssh.exec_command(cmd)
      print("collect success! log file: %s." %(file_name))

      time.sleep(1)

      # 实例化一个 sftp对象,指定连接的通道
      sftp = paramiko.SFTPClient.from_transport(trans)

      print("start download log file[%s]..." %(file_name))
      # 下载文件
      sftp.get("{path}/{name}".format(name=file_name, path=log_root_path), os.path.join(os.getcwd(),file_name))
      print("download success! file path[%s]!" %(os.path.join(os.getcwd(),file_name)))
   except IOError as err:
      print("download fail! err:[%s]!" %(err))
      raise
   except Exception as err:
      raise
   finally:
      print("clean log path[%s] on remote ..." %(log_root_path))
      #rm -rf 操作要慎重
      if re.match("/var/log/pos_log", log_root_path):
         cmd = "rm -rf " + log_root_path
         ssh.exec_command(cmd)
      else:
         print('invalid path[%s] to rm -rf, it is dangerous' %(log_root_path))
         raise "invalid path:"+log_root_path

def create_ssh(addr, port, user, pwd):

   # 实例化一个transport对象
   try:
      trans = paramiko.Transport((addr, port))
      trans.connect(username = user, password = pwd)
      return trans
   except Exception as err:
      print("connect ssh[%s:%d] fail, error: %s" %(addr,port,err))
      return None

def close_ssh(trans):
   trans.close()

# 命令分发
def dispatch_cmd(param, trans):
   switch = {'pos':collect_log, 'zk':collect_zkdatalog}
   if param['cmd'] in switch:
      switch.get(param['cmd'], collect_log)(param, trans)
      return True
   else:
      print("unkown cmd[%s], check it." %(param['cmd']))
      return False

def parse(argv):
   param = {'addr':'127.0.0.1', 'port':9622, 'user':'root', 'password':'123123', 'cmd':'pos', 'zknum':1}
   if argv is None or len(argv) < 2:
      help(argv, param)
      return None
   opts, args = getopt.getopt(argv[1:], "htupc:", ["help", "file=", "cmd=", "zklog-num="])

   if len(opts) == 0 and len(args):
      help(argv, param)
      return None

   for cmd, val in opts:
      if cmd in ('-t'):
         (ip_str, port_str) = val.split(':', 1 )
         patter = re.match(r'^((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})(\.((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})){3}', ip_str)
         if patter is None:
            return None
         param['addr'] = patter.group()
         param['port'] = int(port_str)
         continue
      if cmd in ('-h', '--help'):
         help(argv, param)
         return None
      if cmd == '-u':
          param['user'] = val
          continue
      if cmd == '-p':
          param['password'] = val
          continue
      if cmd in ('-c', '--cmd='):
          param['cmd'] = val
          continue
      help(argv, param)
      return None
   return param

def help(argv, param):
   print("-- help --")
   print("exec: %s -t <ip:port> -u <username> -p <password> -c <cmd>" %(argv[0]))
   print("default: %s -t %s:%d -u %s -p %s -c %s" %(argv[0], param['addr'], param['port'], param['user'], param['password'], param['cmd']))
   print('[cmd]:')
   print(' -- pos, it will download remote pos log on the local machine' )
   print(' -- zk, it will download zookeeper data log on the local machine' )
   print(' -- backup, it will download remote backup log on the local machine' )

# main
def main(argv):
   param = parse(argv)
   if param is None:
      return
   fd = create_ssh(param['addr'], param['port'], param['user'], param['password'])
   if fd is None:
      print("create ssh: %s:%d fail!" %(param['addr'], param['port']))
      return

   print("create ssh: %s:%d success!" %(param['addr'], param['port']))

   try:
      if dispatch_cmd(param, fd):
         print("exec cmd[%s] with ssh<%s:%d> success!" %(param['cmd'], param['addr'], param['port']))
   except Exception as err:
      print(err) 
   finally:
      close_ssh(fd)

if __name__ == "__main__":
   main(sys.argv)