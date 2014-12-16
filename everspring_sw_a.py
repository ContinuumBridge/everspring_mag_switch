#!/usr/bin/env python
# everspring_sw_a.py
# Copyright (C) ContinuumBridge Limited, 2014 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
ModuleName               = "everspring_sw"
BATTERY_CHECK_INTERVAL   = 43200     # How often to check battery (secs)

import sys
import time
import os
from pprint import pprint
import logging
from cbcommslib import CbAdaptor
from cbconfig import *
from twisted.internet import threads
from twisted.internet import reactor

class Adaptor(CbAdaptor):
    def __init__(self, argv):
        logging.basicConfig(filename=CB_LOGFILE,level=CB_LOGGING_LEVEL,format='%(asctime)s %(message)s')
        self.status =           "ok"
        self.state =            "stopped"
        self.apps =             {"binary_sensor": [],
                                 "battery": []}
        # super's __init__ must be called:
        #super(Adaptor, self).__init__(argv)
        CbAdaptor.__init__(self, argv)
 
    def setState(self, action):
        # error is only ever set from the running state, so set back to running if error is cleared
        if action == "error":
            self.state == "error"
        elif action == "clear_error":
            self.state = "running"
        logging.debug("%s %s state = %s", ModuleName, self.id, self.state)
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
        #logging.debug("%s %s onZwaveMessage, message: %s", ModuleName, self.id, str(message))
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
                    level = message["data"]["level"]["value"]
                    logging.debug("%s %s onZwaveMessage, level: %s", ModuleName, self.id, level)
                    self.sendCharacteristic("binary_sensor", self.onOff(level), time.time())
                elif message["commandClass"] == "128":
                     battery = message["data"]["last"]["value"] 
                     logging.info("%s %s battery level: %s", ModuleName, self.id, battery)
                     msg = {"id": self.id,
                            "status": "battery_level",
                            "battery_level": battery}
                     self.sendManagerMessage(msg)
                     self.sendCharacteristic("battery", battery, time.time())
            except:
                logging.debug("%s %s onZwaveMessage, no level", ModuleName, self.id)

    def onAppInit(self, message):
        logging.debug("%s %s %s onAppInit, req = %s", ModuleName, self.id, self.friendly_name, message)
        resp = {"name": self.name,
                "id": self.id,
                "status": "ok",
                "service": [{"characteristic": "binary_sensor", "interval": 0},
                            {"characteristic": "battery", "interval": 600}],
                "content": "service"}
        self.sendMessage(resp, message["id"])
        self.setState("running")

    def onAppRequest(self, message):
        logging.debug("%s %s %s onAppRequest, message = %s", ModuleName, self.id, self.friendly_name, message)
        # Switch off anything that already exists for this app
        for a in self.apps:
            if message["id"] in self.apps[a]:
                self.apps[a].remove(message["id"])
        # Now update details based on the message
        for f in message["service"]:
            if message["id"] not in self.apps[f["characteristic"]]:
                self.apps[f["characteristic"]].append(message["id"])
        logging.debug("%s %s %s apps: %s", ModuleName, self.id, self.friendly_name, str(self.apps))

    def onAppCommand(self, message):
        logging.debug("%s %s %s onAppCommand, req = %s", ModuleName, self.id, self.friendly_name, message)
        if "data" not in message:
            logging.warning("%s %s %s app message without data: %s", ModuleName, self.id, self.friendly_name, message)
        else:
            logging.warning("%s %s %s This is a sensor. Message not understood: %s", ModuleName, self.id, self.friendly_name, message)

    def onConfigureMessage(self, config):
        """Config is based on what apps are to be connected.
            May be called again if there is a new configuration, which
            could be because a new app has been added.
        """
        logging.debug("%s onConfigureMessage, config: %s", ModuleName, config)
        self.setState("starting")

if __name__ == '__main__':
    Adaptor(sys.argv)
