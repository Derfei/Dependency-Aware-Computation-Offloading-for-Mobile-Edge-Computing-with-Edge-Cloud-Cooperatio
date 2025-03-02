# -*- coding: utf-8 -*-
'''
@author: longxin
@version: 1.0
@date:
@changeVersion:
@changeAuthor:
@description: 服务器
'''
import sys
sys.path.append("/home/pi/Desktop/Mobile")
from flask import Flask
from flask import request
from process.processor import *
from model.record import  *
from Executer.executerDeepLearning import excuterDeepLearning
from Executer.excuteDistributedDeepLearning import  excuteDistributedDeepLearningAgent
from Executer.excuteVgg16 import excuteVgg16
from Executer.excuter import ExecuteAgent
from Executer.excuteResnet50 import excuteResnet50
from Executer.excuteVgg16boostVgg19 import  excuteVgg16boostVgg19
from flask.views import request
from model.record import getnetworkinfo
from queue import Queue

# set the excute agent for glaobal
# excuteagent = excuterDeepLearning()
# excuteagent = excuteDistributedDeepLearningAgent()
# excuteagent = ExecuteAgent()
# excuteagent = excuteVgg16()
# excuteagent = excuteVgg16boostVgg19()
# excuteagent = excuteResnet50()
app  = Flask(__name__)
localdeviceid = 1

@app.route('/dojob', methods=['POST'])
def dojob():
    import json
    import datetime
    import time
    import numpy as np

    # 提取任务信息
    data = json.loads(request.get_data().decode(encoding='utf-8'))
    data = data['sendmsgcontent']

    requestdeviceid = data['requestdeviceid']
    applicationid = data['applicationid']
    offloadingpolicyid = data['offloadingpolicyid']
    taskid = data['taskid']
    operationid = data['operationid']
    inputdata = data['inputdata']
    formertasklist = data['formertasklist']
    nexttasklist = data['nexttasklist']
    timecloselist = data['timecostlist']

    if int(data['taskgraphtypeid']) == 1:
        excuteagent = excuteVgg16()
    elif int(data['taskgraphtypeid']) == 2:
        excuteagent = excuteVgg16boostVgg19()
    elif int(data['taskgraphtypeid']) == 3:
        excuteagent = excuteResnet50()
    elif int(data['taskgraphtypeid']) == 4:
        excuteagent = excuteDistributedDeepLearningAgent()
    # 应用信息中获取该任务的所有的前置任务
    actualformertasklist = gettaskFormertask(requestdeviceid, applicationid, taskid)
    # attention 任务结束时间这里需要进行重新设计 应该设计为任务结束的时间
    # 将任务写入前置任务中
    tmptaskdict = {}
    tmptaskdict['formertaskid'] = formertasklist[0]
    tmptaskdict['inputdata'] = inputdata
    tmptaskdict['timecost'] = timecloselist
    writeformertaskinfo(taskid=taskid, requestdeviceid=requestdeviceid, applicationid=applicationid, offloadingpolicyid=offloadingpolicyid,
                        taskdictlist=[tmptaskdict])
    # app.logger.info("Task {0} 写入前置任务 {1} 到离线文件成功".format(taskid, formertasklist))

    # 确认前置任务数据已经全部完成
    if len(actualformertasklist) != 1:
        formertaskdictlist = getformertaskinfo(taskid, requestdeviceid, applicationid, offloadingpolicyid)
        # app.logger.info("该任务需要等待前置任务{0}完成，现在只有{1}完成".format(actualformertasklist, [tmpFormerTask['formertaskid'] for tmpFormerTask
        #                                                                  in formertaskdictlist]))

        if len(formertaskdictlist) == len(actualformertasklist): # 任务已经全部完成 完成任务
            # 执行任务
            #excuteagent = ExecuteAgent()

            inputdatalist = []  # 整理输入数据按照任务id大小进行排序
            for i in range(len(formertaskdictlist)-1):
                for j in range(len(formertaskdictlist)-i-1):
                    if int(formertaskdictlist[j]['formertaskid']) > int(formertaskdictlist[j+1]['formertaskid']):
                        tmp = formertaskdictlist[j]
                        formertaskdictlist[j] = formertaskdictlist[j+1]
                        formertaskdictlist[j+1] = tmp

            for tmp in formertaskdictlist:
                # inputdatalist.append(tmp['inputdata'][0])
                inputdatalist.append(tmp['inputdata'])

            # 合并任务完成时间
            tmpTimeCost = [tmpTime for tmpTime in timecloselist]
            for taskindex in range(len(timecloselist)):
                for tmpformertask in formertaskdictlist:

                    'debug: get cut the send time and exute time'
                    if int(tmpformertask['timecost'][taskindex][0] ) != 0:
                        tmpTimeCost[taskindex] = tmpformertask['timecost'][taskindex]
                        break
                    # if int(tmpformertask['timecost'][taskindex]) != 0:
                    #     tmpTimeCost[taskindex] = tmpformertask['timecost'][taskindex]
                    #     break
            timecloselist = tmpTimeCost
            # print("前置任务不唯一，但是已经完成")
            timecloselist[int(taskid)][0] = time.time()
            print("operation id is: {0} and shape of input is {1}".format(operationid, np.shape(inputdatalist)))
            output = excuteagent.excute(operationid, inputdatalist)
            timecloselist[int(taskid)][1] = time.time()
            # app.logger.info("任务{0}已经完成 nexttasklist 为: {1} 输出为 {2}".format(taskid, nexttasklist, np.shape(output)))

            # 判断是不是最后一个任务
            if len(nexttasklist) == 1 and int(nexttasklist[0]) == -1:
                tmpnewtask = produce_newtask(taskid, timecloselist, taskid, output, requestdeviceid, applicationid,
                                             offloadingpolicyid)
                SendFinal(requestdeviceid, localdeviceid, tmpnewtask)

            else:
                # 生成新的任务
                for tmp in nexttasklist:
                    # app.logger.info("开始生成新的任务{0}".format(tmp))
                    tmpnewtask = produce_newtask(taskid, timecloselist, tmp, output, requestdeviceid, applicationid,
                                                 offloadingpolicyid)
                    # app.logger.info("生成新的任务为{0}".format(tmpnewtask.todict()))
                    SendTask(requestdeviceid, applicationid, offloadingpolicyid, tmp,
                             localdeviceid, tmpnewtask)  # 发送任务到另外的服务器

        else: # 任务还没有全部完成
            app.logger.info("任务{0}进入等待中".format(taskid))
            pass
    else: # 任务已经全部完成
        formertaskdictlist = getformertaskinfo(taskid, requestdeviceid, applicationid, offloadingpolicyid)
        # 执行任务
        #excuteagent = ExecuteAgent()

        inputdatalist = []  # 整理输入数据按照任务id大小进行排序
        for i in range(len(formertaskdictlist) - 1):
            for j in range(len(formertaskdictlist) - i - 1):
                if int(formertaskdictlist[j]['formertaskid']) > int(formertaskdictlist[j + 1]['formertaskid']):
                    tmp = formertaskdictlist[j]
                    formertaskdictlist[j] = formertaskdictlist[j + 1]
                    formertaskdictlist[j + 1] = tmp

        for tmp in formertaskdictlist:
            # inputdatalist.append(tmp['inputdata'][0])
            inputdatalist.append(tmp['inputdata'])
        # 合并任务完成时间
        tmpTimeCost = [tmpTime for tmpTime in timecloselist]
        for taskindex in range(len(timecloselist)):
            for tmpformertask in formertaskdictlist:
                'debug the time cut the time into network time and cpu time'
                if int(tmpformertask['timecost'][taskindex][0]) != 0:
                    tmpTimeCost[taskindex] = tmpformertask['timecost'][taskindex]
                    break
                # if int(tmpformertask['timecost'][taskindex]) != 0:
                #     tmpTimeCost[taskindex] = tmpformertask['timecost'][taskindex]
                #     break
        timecloselist = tmpTimeCost
        timecloselist[int(taskid)][0] = time.time()
        if len(formertaskdictlist) == 1:
            inputdatalist = inputdatalist[0]
        print("operation id is: {0} and shape of input is {1}".format(operationid, np.shape(inputdatalist)))
        output = excuteagent.excute(operationid, inputdatalist)
        timecloselist[int(taskid)][1] = time.time()
        # app.logger.info("任务{0}已经完成 nexttasklist 为: {1} 输出为 {2}".format(taskid, nexttasklist, np.shape(output)))

        # 判断是不是最后一个任务
        if len(nexttasklist) == 1 and int(nexttasklist[0]) == -1:
            tmpnewtask = produce_newtask(taskid, timecloselist, taskid, output, requestdeviceid, applicationid,
                                         offloadingpolicyid)
            SendFinal(requestdeviceid, localdeviceid, tmpnewtask)
        else:
            # 生成新的任务
            for tmp in nexttasklist:
                tmpnewtask = produce_newtask(taskid, timecloselist, tmp, output, requestdeviceid, applicationid,
                                             offloadingpolicyid)
                # 根据id获取应该执行的设备
                # 根据id获取应该执行的设备
                reqUrl = SendTask(requestdeviceid, applicationid, offloadingpolicyid, tmp, localdeviceid,
                                  tmpnewtask)  # 发送任务到另外的服务器

                # app.logger.info("从 设备 {0} 发送任务 {1} 任务内容为 {2} 到设备{3} 执行完任务 {4}".format(localdeviceid, tmp,
                #                                                                       tmpnewtask.todict(), reqUrl,
                #                                                                       taskid))

    return 'OK'


if __name__ == "__main__":
    print("Begin to load the agent")
    # sys.path.append('/home/pi/Desktop/Mobile')
    sys.path.append(r'C:\Users\derfei\Desktop\TMS_Exp\Mobile\Mobile')
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=False)