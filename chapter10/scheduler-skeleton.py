#!/usr/bin/env python2.7
# A skeleton for writing a Mesos scheduler with a custom executor.
#
# For more information, see:
#   * https://github.com/apache/mesos/blob/0.22.2/src/python/interface/src/mesos/interface/__init__.py#L34-L129
#   * https://github.com/apache/mesos/blob/0.22.2/include/mesos/mesos.proto
#
from __future__ import print_function

import site
site.addsitedir('/usr/lib/python2.7/site-packages')
site.addsitedir('/usr/local/lib/python2.7/site-packages')

import logging
import os
import signal
import sys
import time
import uuid
from threading import Thread

from mesos.interface import Scheduler, mesos_pb2
from mesos.native import MesosSchedulerDriver


class ExampleScheduler(Scheduler):
    def __init__(self, executor):
        self.executor = executor

    def registered(self, driver, framework_id, master_info):
        """
          Invoked when the scheduler successfully registers with a Mesos master.
          It is called with the frameworkId, a unique ID generated by the
          master, and the masterInfo which is information about the master
          itself.
        """
        logging.info("Registered with framework ID: {}".format(framework_id.value))

    def reregistered():
        """
          Invoked when the scheduler re-registers with a newly elected Mesos
          master.  This is only called when the scheduler has previously been
          registered.  masterInfo contains information about the newly elected
          master.
        """
        logging.info('Reregistered')

    def disconnected():
        """
          Invoked when the scheduler becomes disconnected from the master, e.g.
          the master fails and another is taking over.
        """
        logging.info('Disconnected')

    def resourceOffers(self, driver, offers):
        """
          Invoked when resources have been offered to this framework. A single
          offer will only contain resources from a single slave.  Resources
          associated with an offer will not be re-offered to _this_ framework
          until either (a) this framework has rejected those resources (see
          SchedulerDriver.launchTasks) or (b) those resources have been
          rescinded (see Scheduler.offerRescinded).  Note that resources may be
          concurrently offered to more than one framework at a time (depending
          on the allocator being used).  In that case, the first framework to
          launch tasks using those resources will be able to use them while the
          other frameworks will have those resources rescinded (or if a
          framework has already launched tasks with those resources then those
          tasks will fail with a TASK_LOST status and a message saying as much).
        """
        for offer in offers:
            logging.info("Received offer with ID: {}".format(offer.id.value))

            task = mesos_pb2.TaskInfo()
            task_id = str(uuid.uuid4())
            task.task_id.value = task_id
            task.slave_id.value = offer.slave_id.value
            task.name = "task {}".format(task_id)
            task.executor.MergeFrom(self.executor)
            task.data = "Hello from task {}!".format(task_id)

            cpus = task.resources.add()
            cpus.name = 'cpus'
            cpus.type = mesos_pb2.Value.SCALAR
            cpus.scalar.value = 0.1

            mem = task.resources.add()
            mem.name = 'mem'
            mem.type = mesos_pb2.Value.SCALAR
            mem.scalar.value = 32

            tasks = [task]
            driver.launchTasks(offer.id, tasks)

    def offerRescinded(self, driver, offer_id):
        """
          Invoked when an offer is no longer valid (e.g., the slave was lost or
          another framework used resources in the offer.) If for whatever reason
          an offer is never rescinded (e.g., dropped message, failing over
          framework, etc.), a framwork that attempts to launch tasks using an
          invalid offer will receive TASK_LOST status updats for those tasks
          (see Scheduler.resourceOffers).
        """
        pass

    def statusUpdate(self, driver, update):
        """
          Invoked when the status of a task has changed (e.g., a slave is
          lost and so the task is lost, a task finishes and an executor
          sends a status update saying so, etc). If implicit
          acknowledgements are being used, then returning from this
          callback _acknowledges_ receipt of this status update! If for
          whatever reason the scheduler aborts during this callback (or
          the process exits) another status update will be delivered (note,
          however, that this is currently not true if the slave sending the
          status update is lost/fails during that time). If explicit
          acknowledgements are in use, the scheduler must acknowledge this
          status on the driver.
        """
        logging.info("Task {} is in state {}".format(
            update.task_id.value, mesos_pb2.TaskState.Name(update.state)))

    def frameworkMessage(self, driver, executor_id, slave_id, message):
        """
          Invoked when an executor sends a message. These messages are best
          effort; do not expect a framework message to be retransmitted in any
          reliable fashion.
        """
        pass

    def slaveLost(self, driver, slave_id):
        """
          Invoked when a slave has been determined unreachable (e.g., machine
          failure, network partition.) Most frameworks will need to reschedule
          any tasks launched on this slave on a new slave.
        """
        pass

    def executorLost(self, driver, executor_id, slave_id, status):
        """
          Invoked when an executor has exited/terminated. Note that any tasks
          running will have TASK_LOST status updates automatically generated.
        """
        pass

    def error(self, driver, message):
        """
          Invoked when there is an unrecoverable error in the scheduler or
          scheduler driver.  The driver will be aborted BEFORE invoking this
          callback.
        """
        logging.error(message)


def main(master):
    logging.basicConfig(level=logging.INFO,
                        format='[%(asctime)s %(levelname)s] %(message)s')

    # Create a new executor
    executor = mesos_pb2.ExecutorInfo()
    executor.executor_id.value = 'ExampleExecutor'
    executor.name = executor.executor_id.value
    executor.command.value = os.path.abspath('./executor-skeleton.py')

    # Create a new framework
    framework = mesos_pb2.FrameworkInfo()
    framework.user = ''  # the current user
    framework.name = 'ExampleFramework'
    framework.checkpoint = True

    implicitAcknowledgements = 1

    if os.getenv('EXAMPLE_AUTHENTICATE'):
        logging.info('Enabling framework authentication')

        credential = mesos_pb2.Credential()
        credential.principal = os.getenv('EXAMPLE_PRINCIPAL')
        credential.secret = os.getenv('EXAMPLE_SECRET')
        framework.principal = os.getenv('EXAMPLE_PRINCIPAL')

        driver = MesosSchedulerDriver(
            ExampleScheduler(executor),
            framework,
            master,
            implicitAcknowledgements,
            credential
        )
    else:
        framework.principal = framework.name

        driver = MesosSchedulerDriver(
            ExampleScheduler(executor),
            framework,
            master,
            implicitAcknowledgements
        )

    def signal_handler(signal, frame):
        logging.info('Shutting down')
        driver.stop()

    # driver.run() blocks, so we run it in a separate thread.
    # This way, we can catch a SIGINT to kill the framework.
    def run_driver_thread():
        status = 0 if driver.run() == mesos_pb2.DRIVER_STOPPED else 1
        driver.stop()  # Ensure the driver process terminates
        sys.exit(status)

    driver_thread = Thread(target=run_driver_thread, args=())
    driver_thread.start()

    logging.info('Scheduler running, Ctrl-C to exit')
    signal.signal(signal.SIGINT, signal_handler)

    # Block the main thread while the driver thread is alive
    while driver_thread.is_alive():
        time.sleep(1)

    logging.info('Framework finished.')
    sys.exit(0)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: {} <mesos_master>".format(sys.argv[0]))
        sys.exit(1)
    else:
        main(sys.argv[1])
