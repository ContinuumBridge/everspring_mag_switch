#!/usr/bin/env python
# everspring_sw_a.py
# Copyright (C) ContinuumBridge Limited, 2014 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
ModuleName               = "everspring_sw"
BATTERY_CHECK_INTERVAL   = 7200     # How often to check battery (secs)
TIME_CUTOFF              = 43200    # 12 hours. Data older than this is considered "stale"

import sys
import time
import os
from pprint import pprint
from cbcommslib import CbAdaptor
from cbconfig import *
from twisted.internet import threads
from twisted.internet import reactor

class Adaptor(CbAdaptor):
    def __init__(self, argv):
        self.status =           "ok"
        self.state =            "stopped"
        self.apps =             {"binary_sensor": [],
                                 "battery": []}
        self.lastBinaryTime =   0
        self.lastBatteryTime =  0
        # super's __init__ must be called:
        #super(Adaptor, self).__init__(argv)
        CbAdaptor.__init__(self, argv)
 
    def setState(self, action):
        # error is only ever set from the running state, so set back to running if error is cleared
        if action == "error":
            self.state == "error"
        elif action == "clear_error":
            self.state = "running"
        msg = {"id": self.id,
               "status": "state",
               "state": self.state}
        self.sendManagerMessage(msg)

    def sendCharacteristic(self, characteristic, data, timeStamp):
        msg = {"id": self.id,
               "content": "characteristic",
               "characteristic": characteristic,
               "data": data,
               "timeStamp": timeStamp}
        for a in self.apps[characteristic]:
            self.sendMessage(msg, a)

    def checkBattery(self):
        cmd = {"id": self.id,
               "request": "post",
               "address": self.addr,
               "instance": "0",
               "commandClass": "128",
               "action": "Get",
               "value": ""
              }
        self.sendZwaveMessage(cmd)
        reactor.callLater(BATTERY_CHECK_INTERVAL, self.checkBattery)

    def onOff(self, boolean):
        if boolean:
            return "on"
        elif not boolean:
            return "off"

    def onZwaveMessage(self, message):
        #self.cbLog("debug", "onZwaveMessage, message: " + str(message))
        if message["content"] == "init":
            cmd = {"id": self.id,
                   "request": "get",
                   "address": self.addr,
                   "instance": "0",
                   "commandClass": "48",
                   "value": "1"
                  }
            self.sendZwaveMessage(cmd)
            cmd = {"id": self.id,
                   "request": "get",
                   "address": self.addr,
                   "instance": "0",
                   "commandClass": "128"
                  }
            self.sendZwaveMessage(cmd)
            reactor.callLater(100, self.checkBattery)
        elif message["content"] == "data":
            try:
                if message["commandClass"] == "48":
                    updateTime = message["data"]["level"]["updateTime"] 
                    if updateTime != self.lastBinaryTime and time.time() - updateTime < TIME_CUTOFF:
                        level = message["data"]["level"]["value"]
                        self.cbLog("debug", "onZwaveMessage, level: " + str(level))
                        self.sendCharacteristic("binary_sensor", self.onOff(level), time.time())
                        self.lastBinaryTime = updateTime
                elif message["commandClass"] == "128":
                    updateTime = message["data"]["last"]["updateTime"]
                    if (updateTime != self.lastBatteryTime) and (time.time() - updateTime < TIME_CUTOFF):
                        battery = message["data"]["last"]["value"] 
                        self.cbLog("debug", "battery level: " + str(battery))
                        msg = {"id": self.id,
                               "status": "battery_level",
                               "battery_level": battery}
                        self.sendManagerMessage(msg)
                        self.sendCharacteristic("battery", battery, time.time())
                        self.lastBatteryTime = updateTime
            except:
                self.cbLog("debug", "onZwaveMessage, no level")

    def onAppInit(self, message):
        self.cbLog("debug", "onAppInit, req: " + str(message))
        resp = {"name": self.name,
                "id": self.id,
                "status": "ok",
                "service": [{"characteristic": "binary_sensor", "interval": 0},
                            {"characteristic": "battery", "interval": 600}],
                "content": "service"}
        self.sendMessage(resp, message["id"])
        self.setState("running")

    def onAppRequest(self, message):
        self.cbLog("debug", "onAppRequest, message: " + str(message))
        # Switch off anything that already exists for this app
        for a in self.apps:
            if message["id"] in self.apps[a]:
                self.apps[a].remove(message["id"])
        # Now update details based on the message
        for f in message["service"]:
            if message["id"] not in self.apps[f["characteristic"]]:
                self.apps[f["characteristic"]].append(message["id"])
        self.cbLog("debug", "apps: " + str(self.apps))

    def onAppCommand(self, message):
        self.cbLog("debug", "onAppCommand, req: " + str(message))
        if "data" not in message:
            self.cbLog("warning", "app message without data: " + str(message))
        else:
            self.cbLog("warning", "This is a sensor. Message not understood: " + str(message))

    def onConfigureMessage(self, config):
        """Config is based on what apps are to be connected.
            May be called again if there is a new configuration, which
            could be because a new app has been added.
        """
        self.setState("starting")

if __name__ == '__main__':
    Adaptor(sys.argv)
