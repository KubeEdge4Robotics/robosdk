
Install RoboSDK from Source
============================

* Prerequisites

  * `Python >= 3.6, < 3.9 <https://www.python.org/downloads/>`_

* Enable Virtual Environment

  * Mac OS / Linux

    .. code-block:: sh

       # If your environment is not clean, create a virtual environment firstly.
       python -m venv robo_venv
       source ./robo_venv/bin/activate

  * Windows

    .. code-block:: powershell

       # If your environment is not clean, create a virtual environment firstly.
       python -m venv robo_venv
       # You may need this for SecurityError in PowerShell.
       Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Unrestricted
       # Activate the virtual environment.
       .\robo_venv\Scripts\activate

* Install RoboSDK

  .. code-block:: sh

       # Git Clone the whole source code.
       git clone https://github.com/kubeedge/robosdk.git

       # Build the pip package
       python3 setup.py bdist_wheel

       # Install the pip package
       pip3 install dist/robosdk*.whl