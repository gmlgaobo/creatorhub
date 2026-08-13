from __future__ import annotations

import asyncio
import sys

import servicemanager
import win32event
import win32service
import win32serviceutil

from .server import create_server


class CreatorHubService(win32serviceutil.ServiceFramework):
    _svc_name_ = "CreatorHubService"
    _svc_display_name_ = "CreatorHub Background Service"
    _svc_description_ = "CreatorHub monitoring, official API, HTTPS and backup service."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.server = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.server is not None:
            self.server.should_exit = True
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("CreatorHub service starting")
        self.server = create_server()
        asyncio.run(self.server.serve())
        servicemanager.LogInfoMsg("CreatorHub service stopped")


def service_main() -> None:
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(CreatorHubService)
        servicemanager.StartServiceCtrlDispatcher()
        return
    win32serviceutil.HandleCommandLine(CreatorHubService)
