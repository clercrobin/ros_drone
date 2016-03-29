#! /usr/bin/env python
# -*- coding: utf-8 -*-

import curses
import math
import rospy
from flow_control_py.srv import *

def main(stdscr):
    rospy.init_node('flow_teleop', anonymous=True)
    rospy.wait_for_service('flow_command')
    flow_command = rospy.ServiceProxy('flow_command',FlowCommand)
    rate = rospy.Rate(10) 
    keycode = -1
    command = 'Stop'
    stdscr.addstr("Flow commands\n")
    stdscr.addstr(" - UP         : start flow control\n")
    stdscr.addstr(" - LEFT/RIGHT : control angular z\n")
    stdscr.addstr(" - any key    : stop flow control\n")
    stdscr.addstr(" - ESC        : stop flow control and exit\n")
    while (not rospy.is_shutdown()) and (keycode != 27): 
        keycode = stdscr.getch() 
        if   keycode == curses.KEY_UP    : command = 'Go'
        elif keycode == curses.KEY_LEFT  : command = 'Left'
        elif keycode == curses.KEY_RIGHT : command = 'Right'
        else                             : command = 'Stop'
        flow_command(command)
        rate.sleep()

if __name__ == '__main__':
    try:
        curses.wrapper(main)
    except rospy.ROSInterruptException:
        pass
