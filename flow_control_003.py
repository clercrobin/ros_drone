#!/usr/bin/env python

import roslib
import rospy
import time
import numpy as np
import cv2
from geometry_msgs.msg import Twist
from sensor_msgs.msg import CompressedImage

from flow_control_py.srv import *

user_interrupt_duration = 1.00 # seconds
user_angular_speed      = 1.00 # rad/s
user_linear_speed       = 0.50 # m/s
controller_linear_speed = 0.60 # m/s

flow_display_scale      = 5.00
angular_scale           = 0.10
max_angular_twist       = 1.00
flow_top                = 160
flow_bottom             = 235
flow_top_ref_ground     = 230
flow_bottom_ref_ground     = 235

width  = 320
height = 240


# This is a controller that stabilizes the drone trajectory when it
# should go ahead. It is base on the computation of optical flow
# generated by the ground, which is textured in the simulated
# environment.
class FlowController:

    def __init__(self):
        self.service      = rospy.Service   ('flow_command',          FlowCommand,     self.on_command               )
        self.sub          = rospy.Subscriber('/image_in/compressed',  CompressedImage, self.on_image,  queue_size = 1)
        self.pub          = rospy.Publisher ('cmd_vel',               Twist,                           queue_size = 1)
        self.ipub         = rospy.Publisher ('/image_out/compressed', CompressedImage,                 queue_size = 1)
        self.prvs         = None
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
        self.time_since_too_near = 0
        self.i = 0
        self.moy = [0,0]
        self.prev = 0
        self.prevprev = 0
        self.prevprevprev = 0

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

    # This tells if our automatic control should be running.
    def should_be_controlled(self):
        if self.stopped : return False
        if not self.controlled :
            duration        = rospy.Time.now() - self.last_time
            self.controlled = duration.to_sec() > user_interrupt_duration
        return self.controlled

    # The twist computed by the control is self.go_twist. This method
    # displays it on the image (a circle on the top). Indeed, only the
    # angular.z is represented graphically.
    def display_twist(self, image_out):
        pos = 160 + int(-160*self.go_twist.angular.z/max_angular_twist)
        cv2.circle(image_out,(pos,20),10, (0,255,0))
        cv2.line(image_out,(160,5),(160,35), (0,255,0))
        
    # This function computes the average of the flow observed in a
    # rectangular area. It also displays the area and the flow on the
    # output image.
    def flow_in_area(self, flow, image_out, minw, maxw, minh, maxh, color):
        area    = (maxw-minw)*(maxh-minh)
        subflow = flow[minh:maxh,minw:maxw,:]
        avgflow = np.sum(subflow, axis=(0,1)) / area
        cv2.rectangle(image_out, (minw,minh), (maxw,maxh), color)
        origin  = (int((minw+maxw)/2), int((minh+maxh)/2))
        end     = (int(origin[0] + flow_display_scale*avgflow[0]), int(origin[1] + flow_display_scale*avgflow[1]))
        cv2.line(image_out, origin, end, color)
        return avgflow;

    # This is our control. 
    def apply_control(self, next, image_out):
        flow          = cv2.calcOpticalFlowFarneback(self.prvs, next, 0.5, 3, 10, 3, 5, 1.2, 0)
        left_flow     = self.flow_in_area(flow, image_out,   5,  50, flow_top, flow_bottom, (255,   0,   0))
        right_flow    = self.flow_in_area(flow, image_out, 270, 315, flow_top, flow_bottom, (  0,   0, 255))
        middle_flow   = self.flow_in_area(flow, image_out, 120, 200, flow_top_ref_ground, flow_bottom_ref_ground, (255, 255,   0))
        left_flow     = left_flow  - middle_flow
        right_flow    = right_flow - middle_flow
        #print("left_flow : " + str(left_flow[0]) + " middle : "+str(middle_flow[0])+" right_flow : " + str(right_flow[0]))
        print("middle : " + str(middle_flow)) 
       # print("left : " + str(left_flow))
       # print("right : " + str(right_flow))
        self.moy[0] = (self.i*self.moy[0]+middle_flow[0])/(self.i+1)
        self.i+=1
        currentmoy = (middle_flow[0]+self.prev+self.prevprev+self.prevprevprev)/4
        if(time.clock() - self.time_since_too_near > 0.5):
            angular_speed = - angular_scale*(left_flow[0] + right_flow[0])#/abs(middle_flow[0])
            if   angular_speed < -max_angular_twist : angular_speed = -max_angular_twist
            elif angular_speed >  max_angular_twist : angular_speed =  max_angular_twist
            self.go_twist.angular.z = angular_speed
            self.display_twist(image_out)
            if (abs(currentmoy)<0.0005*self.moy[0]):
                self.go_twist.linear.x = -0.1
                self.time_since_too_near = time.clock()
                self.go_twist.angular.z = max_angular_twist/2
            elif (abs(currentmoy)<0.005*self.moy[0]):
                self.go_twist.linear.x = 0.05
            #elif (abs(currentmoy)<0.05*self.moy[0]):
             #   self.go_twist.linear.x = 0.1
            else:
                self.go_twist.linear.x = 0.6
               # self.go_twist.linear.x = 0.1* (currentmoy/self.moy[0])**2
        self.prevprevprev = self.prevprev
        self.prevprev = self.prev
        self.prev = middle_flow[0]
        return self.go_twist
        
    # This is the image topic callback. The control is reconsider at each new image.
    def on_image(self, ros_data):
        compressed_in = np.fromstring(ros_data.data, np.uint8)
        image_in      = cv2.imdecode(compressed_in, cv2.CV_LOAD_IMAGE_COLOR)
        if self.prvs == None :
            self.prvs = cv2.resize(cv2.cvtColor(image_in,cv2.COLOR_BGR2GRAY), (width,height))
        else:
            next      = cv2.resize(cv2.cvtColor(image_in,cv2.COLOR_BGR2GRAY), (width,height))
            image_out = cv2.resize(image_in, (width,height))
            if self.should_be_controlled() : self.pub.publish(self.apply_control(next, image_out))
            self.prvs = next

            msg              = CompressedImage()
            msg.header.stamp = rospy.Time.now()
            msg.format       = "jpeg"
            msg.data         = np.array(cv2.imencode('.jpg', image_out)[1]).tostring()
            self.ipub.publish(msg)

if __name__ == '__main__':
    rospy.init_node('flow_control', anonymous=True)
    try:
        flow_controller = FlowController()
        rospy.spin()
    except KeyboardInterrupt:
        print "Shutting down flow controller"

