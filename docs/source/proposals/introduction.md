# Introduction

`RoboSDK` is an open-source project that aims to democratize robotics development by providing developers with convenient access to robot datasets, cloud resources, and hardware abstraction. Our mission is to lower the barriers to entry in the robotics domain and enable ambitious projects at all levels of expertise. By leveraging the power of cloud-native technologies, `RoboSDK` enhances the capabilities of robots and opens up new possibilities for applications in various industries, including manufacturing, healthcare, logistics, and more.

## Significance

Cloud-native robotics is revolutionizing the robotics industry, enabling robots to adapt and learn from real-world experiences continuously. With `RoboSDK`, we seek to drive this transformation by providing a comprehensive and user-friendly framework for cloud-native robotics application development.

Cloud-native robotics is a cutting-edge approach that leverages cloud computing and services to enhance the capabilities of robots. By offloading computation and data storage to the cloud, robots can access vast amounts of data, powerful machine learning algorithms, and computational resources, enabling them to perform complex tasks and make data-driven decisions. This approach revolutionizes the robotics industry, enabling robots to adapt and learn from real-world scenarios continuously.

## Challenges Faced by Developers

Integrating cloud services with robots has traditionally been a daunting task for developers due to various challenges:

- **Hardware Diversity:** Robots and sensors come in various Protocols and Drivers, making hardware integration complex and time-consuming.

- **Robot Operating System (ROS) Compatibility:** ROS versions and standards may differ across platforms, causing compatibility issues.

- **Cloud Service Integration:** Integrating cloud services often requires deep knowledge of specific APIs and complex configurations.

- **Across Component Integration:** To achieve complete application development, we require a common API and research platform for sharing code, data, and models across services, control, algorithms, and data processing modules. However, despite its long history and extensive capabilities, `ROS` can be challenging for new users without the necessary expertise or time to fully understand the software stack.

## Concepts

Conceptual overviews provide relatively high-level, general background information about key aspects of `RoboSDK`.

`RoboSDK` is a middleware on top of the robot operating system (ROS). It provides a consistent set of hardware-independent mid-level APIs to control different robots. These are the concepts that will help you get started understanding the basics of `RoboSDK`.

- **ROS**: The Robot Operating System (ROS) is a set of software libraries and tools that help you build robot applications. From drivers to state-of-the-art algorithms, and with powerful developer tools, ROS has what you need for your next robotics project. Representative work includes: [ROS 1](https://wiki.ros.org/), [ROS 2](http://docs.ros.org/), and [OpenHarmony](https://www.openharmony.cn/).

- **RoboArtisan**: `RoboArtisan` is a series of cloud-native robotics solutions that aims to simplify and democratize the research of sophisticated robotics scenes. Representative work includes: `RoboOMS`, `RoboSS`, `RoboAI`.

- **RoboOMS**: The Robot Operation Management Service (RoboOMS) is a cloud-native robotics solution built on [KubeEdge](https://github.com/kubeedge/kubeedge). It provides a foundation for managing robot-cloud-edge communication, facilitating multi-robot collaboration, deploying applications, and conducting operations.

- **RoboSS**: The Robot Simulation Service (RoboSS) is a cloud-native robotics solution built on [O3DE](https://github.com/o3de/o3de). It provides a simulation framework for cloud-native scenarios, allowing users to simulate robot scenarios, generate data, train skills, and experiment with digital twins using open-source simulators.

- **RoboAI**: The Robot Artificial Intelligence Service (RoboAI) is a cloud-native robotics solution for building and deploying AI solutions. Representative work includes: [sedna](https://github.com/kubeedge/sedna).