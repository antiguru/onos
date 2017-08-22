#!env /usr/bin/python

import json
import os
import pty
import subprocess
import random
import time

class Process(object):
    def run(self, *args, **kwargs):
        command = map(str, args)
        print(command)
        env = os.environ.copy()
        env["ONOS_WEB_USER"] = "onos"
        env["ONOS_WEB_PASS"] = "rocks"
        kwargs["env"] = env
        return subprocess.Popen(command, **kwargs)

class Setup(object):
    def __init__(self):
        pass

    def onos(self, command, **kwargs):
        # Run ONOS command
        return Process().run("tools/package/bin/onos", command, **kwargs)

    def onos_json(self, command):
        onos = self.onos(command, stdout=subprocess.PIPE)
        for line in onos.stdout.readlines():
            print line
            result = json.loads(line)
        onos.wait()
        return result

    def get_hosts(self):
        onos = self.onos("hosts", stdout=subprocess.PIPE)
        hosts = []
        for line in onos.stdout.readlines():
            parts = line.strip().split(', ')
            host = {}
            for part in parts:
                p = part.split('=')
                host[p[0]] = p[1]
            hosts.append(host)
        onos.wait()
        return hosts

    def get_summary(self):
        summary =  self.onos_json("summary -j")
        print summary
        return summary

    def run_experiment(self, k):
        host_count = k*k*k/4
        # Build and start ONOS
        buck = Process().run("tools/build/onos-buck", "run", "onos-local", "--", "clean", stdout=subprocess.PIPE)
        #buck = Process().run("tools/build/onos-buck", "run", "onos-local", stdout=subprocess.PIPE)
        for line in iter(buck.stdout.readline, ''):
            if "Waiting for karaf.log" in line:
                print "ONOS started"
                break
        time.sleep(3)

        self.onos("wait org.onosproject.net.driver.DefaultDriverProviderService").wait()
        time.sleep(3)

        self.onos("app activate org.onosproject.null").wait()
        self.onos("null-simulation start fattree,%d" % k).wait()

        retry = 0
        while self.get_summary()['hosts'] < host_count:
            time.sleep(.1)
            retry += 1
            if retry > 20:
                print "ABORTING: timeout waiting for hosts"
                buck.kill()
                return

        time.sleep(3)

        random.seed(host_count)

        hosts = self.get_hosts()
        pairs = [tuple(sorted([random.randint(0, len(hosts) - 1) for x in xrange(2)])) for p in xrange(5)]


        intent_count = 0
        seen_pairs = set()
        for pair in pairs:
            if pair[0] == pair[1]:
                continue
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            self.onos("add-point-intent --protect %s %s" % (hosts[pair[0]]['location'], hosts[pair[1]]['location'])).wait()
            self.onos("add-point-intent --protect %s %s" % (hosts[pair[1]]['location'], hosts[pair[0]]['location'])).wait()

            intent_count += 2
        while self.get_summary()['intents'] < intent_count:
            time.sleep(1)

        self.onos("intents -j").wait()

        log = self.onos("log:display PointToPointIntentCompiler | grep --color never DP", stdout=subprocess.PIPE)
        data = log.communicate()[0]
        print data
        with open('experiment1_%d.log' % (k), 'wb') as f:
            f.write(data)

        buck.kill()

def main():
    setup = Setup()
    setup.run_experiment(8)
if __name__ == "__main__":
    main()
