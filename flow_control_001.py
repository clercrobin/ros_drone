#!/usr/bin/env python

import roslib
import rospy
from geometry_msgs.msg import Twist

from flow_control_py.srv import *

user_interrupt_duration = 1    # seconds
user_angular_speed      = 1    # rad/s
user_linear_speed       = 0.5  # m/s
controller_linear_speed = 1    # m/s


# This is fake, since no input image is provided. Nevertheless, this
# shows how user emergency stops (from flow_command clients) as well
# as orientation modifications can interact with a controller.
class FlowController:

    def __init__(self):
        self.service      = rospy.Service  ('flow_command', FlowCommand, self.on_command)
        self.pub          = rospy.Publisher('cmd_vel',      Twist,       queue_size=1)
        self.controlled   = False
        self.stopped      = True
        self.last_time    = rospy.Time.now()
        self.stop_twist   = Twist()
        self.go_twist     = Twist()
        self.left_twist   = Twist()
        self.right_twist  = Twist()         
        self.go_twist.linear.x     =  controller_linear_speed
        self.left_twist.linear.x   =  user_linear_speed
        self.right_twist.linear.x  =  user_linear_speed
        self.left_twist.angular.z  =  user_angular_speed
        self.right_twist.angular.z = -user_angular_speed

    # This is the service.
    def on_command(self,req):
        if req.command == 'Stop' :
            self.stopped    = True
            self.pub.publish(self.stop_twist)
        elif req.command == 'Go' :
            self.controlled = True
            self.stopped    = False
        elif req.command == 'Left' :
            self.controlled = False
            self.stopped    = False
            self.last_time  = rospy.Time.now()
            self.pub.publish(self.left_twist)
        elif req.command == 'Right' :
            self.controlled = False
            self.stopped    = False
            self.last_time  = rospy.Time.now()
            self.pub.publish(self.right_twist)
        return FlowCommandResponse()

    # This tells if our automatic control (fake here) should be
    # running.
    def should_be_controlled(self):
        if self.stopped : return False
        if not self.controlled :
            duration        = rospy.Time.now() - self.last_time
            self.controlled = duration.to_sec() > user_interrupt_duration
        return self.controlled

    # This is the control. Here, it consists of going ahead blindly.
    def control(self):
        self.pub.publish(self.go_twist)

if __name__ == '__main__':
    rospy.init_node('flow_control', anonymous=True)
    try:
        flow_controller = FlowController()
        # As we have no periodic image processing, we use the only
        # update periodically the control.
        rate            = rospy.Rate(10) # 10hz
        while not rospy.is_shutdown():
            if flow_controller.should_be_controlled() : flow_controller.control()
            rate.sleep()
    except KeyboardInterrupt:
        print "Shutting down flow controller"

