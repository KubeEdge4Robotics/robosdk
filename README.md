## RoboSDK

### [![LOGO](./docs/source/_static/logo150x150.png)](https://github.com/kubeedge/robosdk)


### What is RoboSDK

`RoboSDK` is a light weight, high-level interface which provides hardware independent APIs for robotic control and perception.
The goal of this project is to abstract away the low-level controls for developing APPs that runs on an industrial robot in an easy-to-use way.

### Features

`RoboSDK` provide the following features:

- Defining the Running World
    - A `World` represent an environment which the robot launch, such as interactive maps, active objects and scenarios.
    - `simulator`: it provides some predefined scenarios such as Gazebo, and the reusable wheels for building new `World`.
    
- Sensor-Based Control for Registered Robots
    - Object-oriented, unified interface for equivalent sensors, such as : `Camera`, `Lidar`, `IMU` and `Audio`. 
      Therefore, they are guaranteed to have the same interface defined by the base class, for example, 
      `Camera` would have `get_rgb`, `get_depth` as its member function, and their behavior would be the same across hardware.
    - A `Robot` instance consists of multiple components of sensors which were extended the `BaseClass` respectively. `Robot` and `Sensor` is one-to-many.
    - A `Robot` is controlled by invoking the `Sensor` interface. The robots are managed by combining multiple configurations of each sensor.
    - Interconnection with Vendor-defined interface, like: socket-base gait change.
    
- Plug-in-and-play Algorithms
    - Localize
    - Perception
    - Navigation
    - Cloud-Edge Service

- Robot Operating System Backend mapping
  ```text
  It provides a full-stack abstraction for Robot Operating System, such as message manager.
  ```
  
  - Ros1 [stable]
  - Ros2 [rc]
  - openHarmony [alpha]
  

### Installation

- Prerequisites
  - Robot Operating System: such as [Ros noetic](http://wiki.ros.org/noetic/installation/ubuntu) 

- Enable Virtual Environment
  - Mac OS / Linux

    ```sh
    # If your environment is not clean, create a virtual environment firstly.
    python -m venv robo_venv
    source ./robo_venv/bin/activate
    ```

  - Windows

    ```powershell
    # If your environment is not clean, create a virtual environment firstly.
    python -m venv robo_venv

    # You may need this for SecurityError in PowerShell.
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Unrestricted

    # Activate the virtual environment.
    .\robo_venv\Scripts\activate
    ```
    
- Install RoboSDK

    ```sh
  # Git Clone the whole source code.
  git clone https://github.com/kubeedge/robosdk.git
  
  # Build the pip package
  python3 setup.py bdist_wheel
    
  # Install the pip package 
  pip3 install dist/robosdk*.whl
  ```
  
### Show Cases

- Case I - [Legged-Robot Auto Gait Change](./examples/ysc_x20/auto_gait_change)
- Case II - [Arm-Robot Teleoperation](./examples/scout_arm/teleoperation)


### Supported

As we are currently fully tested in the following Robots/sensors, which is considered to be well supported :

#### Robot
 - [x20](https://www.deeprobotics.cn/products_jy_3.html)
 - [scout](https://global.agilex.ai/products/scout-mini)

### [Cite Us](./CITATION)

### License

Copyright 2021 The KubeEdge Authors. All rights reserved.

Licensed under the [Apache License](./LICENSE), Version 2.0.