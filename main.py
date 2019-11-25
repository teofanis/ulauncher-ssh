import glob

from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent, PreferencesUpdateEvent, PreferencesEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from os.path import expanduser
import logging
import subprocess
import os
import re
import shlex

logger = logging.getLogger(__name__)

class SshExtension(Extension):

    def __init__(self):
        super(SshExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())
        self.subscribe(PreferencesUpdateEvent, PreferencesUpdateEventListener())
        self.subscribe(PreferencesEvent, PreferencesEventListener())
        self.home = expanduser("~")

    def parse_ssh_config(self):
        hosts = []
        index = -1

        try:
            with open(self.home + "/.ssh/config", "r") as ssh_config:
                lines = ssh_config.readlines()
                hosts = self.parse_with_includes(lines, [])
        except:
            logger.debug("ssh config not found!")

        return hosts

    def parse_with_includes(self, lines, hosts = []):
        tmp_hosts = []
        includes = self.parse_config(lines, tmp_hosts)

        for host in tmp_hosts:
            hosts.append(host)

        for inc in includes:
            self.parse_with_includes(self.read_include(inc), hosts)

        return hosts

    def parse_config(self, ssh_config, hosts):
        index = -1
        includes = []

        for line in ssh_config:
            line_lc = line.lower().strip().strip("\n")

            if self.is_host_line(line_lc):
                hosts.append({
                    "host": line_lc[5:]
                })
                index += 1

            if line_lc.startswith("hostname "):
                hosts[index]["hostname"] = line_lc[9:]

            if line_lc.startswith("include "):
                includes.append(line[8:].strip().strip("\n"))

        return includes

    def read_include(self, line):
        path = (self.home + "/.ssh/" + line)
        for fn in glob.iglob(path):
            if os.path.isfile(fn):
                with open(fn, "r") as cf:
                    return cf.readlines()

    def is_host_line(self, line_lc):
        return line_lc.startswith("host ") and "*" not in line_lc and "keyalgorithms" not in line_lc

    def parse_known_hosts(self):
        hosts = []
        host_regex = re.compile("^[a-zA-Z0-9\\-\\.]*(?=(,.*)*\\s)")

        try:
            with open(self.home + "/.ssh/known_hosts", "r") as known_hosts:
                for line in known_hosts:
                    line_lc = line.lower()
                    match = host_regex.match(line_lc)

                    if match:
                        hosts.append(match.group().strip())
        except:
            logger.debug("known_hosts not found!")

        return hosts

    def launch_terminal(self, addr):
        logger.debug("Launching connection " + addr)
        shell = os.environ["SHELL"]

        cmd = self.terminal_cmd.replace("%SHELL", shell).replace("%CONN", addr)

        if self.terminal:
            subprocess.Popen([self.terminal, self.terminal_arg, cmd], cwd=self.home)

class ItemEnterEventListener(EventListener):

    def on_event(self, event, extension):
        data = event.get_data()
        extension.launch_terminal(data)

class PreferencesUpdateEventListener(EventListener):

    def on_event(self, event, extension):

        if event.id == "ssh_launcher_terminal":
            extension.terminal = event.new_value
        elif event.id == "ssh_launcher_terminal_arg":
            extension.terminal_arg = event.new_value
        elif event.id == "ssh_launcher_terminal_cmd":
            extension.terminal_cmd = event.new_value
        elif event.id == "ssh_launcher_use_known_hosts":
            extension.use_known_hosts = event.new_value
        elif event.id == "ssh_launcher_dedup_by_hostname":
            extension.dedup_by_hostname = event.new_value

class PreferencesEventListener(EventListener):

    def on_event(self, event, extension):
        extension.terminal = event.preferences["ssh_launcher_terminal"]
        extension.terminal_arg = event.preferences["ssh_launcher_terminal_arg"]
        extension.terminal_cmd = event.preferences["ssh_launcher_terminal_cmd"]
        extension.use_known_hosts = event.preferences["ssh_launcher_use_known_hosts"]
        extension.dedup_by_hostname = event.preferences["ssh_launcher_dedup_by_hostname"]

class KeywordQueryEventListener(EventListener):

    def on_event(self, event, extension):
        icon = "images/icon.png"
        items = []
        arg = event.get_argument()

        hosts = extension.parse_ssh_config()

        if extension.use_known_hosts == "True":
            known_hosts = extension.parse_known_hosts()

            if extension.dedup_by_hostname == "True":
                hostnames = map(lambda x: x["hostname"], hosts)
                known_hosts = filter(lambda x: not x in hostnames, known_hosts)

            hosts += map(lambda x: {"host": x}, known_hosts)

        hosts = list(map(lambda x: x["host"], hosts))
        hosts.sort()

        if arg is not None and len(arg) > 0:
            hosts = filter(lambda x: arg in x, hosts)

        for host in hosts:
            items.append(ExtensionResultItem(icon=icon,
                                            name=host,
                                            description="Connect to '{}' with SSH".format(host),
                                            on_enter=ExtensionCustomAction(host, keep_app_open=False)))

        # If there are no results, let the user connect to the specified server.
        if len(items) <= 0:
            items.append(ExtensionResultItem(icon=icon,
                                            name=arg,
                                            description="Connect to {} with SSH".format(arg),
                                            on_enter=ExtensionCustomAction(arg, keep_app_open=False)))

        return RenderResultListAction(items)

if __name__ == '__main__':
    SshExtension().run()
