# Contributing Guidelines

The SIG Robotics focuses on technical discussion, API definition, reference architecture, implementation in robots, to enable the cloud ability(storage, AI) to be applied to the robots on edge.
We are excited about the prospect of you joining our [community](https://github.com/kubeedge/community). The KubeEdge community abides by the CNCF [code of conduct](CODE-OF-CONDUCT.md). 

- [Open issues](https://github.com/kubeedge/robosdk/issues) for reporting bugs and requesting new features.
- Contribute to [examples](https://github.com/kubeedge/robosdk/tree/main/examples) to share your problem modeling to others.
- Contribute to [scenarios](https://github.com/kubeedge/robosdk/tree/main/simulator/scenarios) to provide more meaningful simulation environments.
- Contribute to [configs](https://github.com/kubeedge/robosdk/tree/main/configs) to provide more meaningful configs for robots/sensors.
- Contribute to [algorithms](https://github.com/kubeedge/robosdk/tree/main/robosdk/algorithms) to enrich robotics algorithm.
- Contribute to [cloud_robotics](https://github.com/kubeedge/robosdk/tree/main/robosdk/cloud_robotics) to make cloud services support for robots.
- Contribute to [backend](https://github.com/kubeedge/robosdk/tree/main/robosdk/backend) to make it support more robot-operating systems.
- Contribute to [sensors](https://github.com/kubeedge/robosdk/tree/main/robosdk/sensors) to make it support more sensors of robot.
- Contribute to [tests](https://github.com/kubeedge/robosdk/tree/main/tests) to make it more reliable and stable.
- Contribute to [documentation](https://github.com/kubeedge/robosdk/tree/main/docs) to make it straightforward for everyone.

## Notes

- Check Style

  Please make sure lint your code, and pass the code checking before pull request.

  We have prepared a configuration file for isort and flake8 to lint.

  ```sh
  # Install isort.
  pip install isort

  # Automatically re-format your imports with isort.
  isort --settings-path .github/linters/tox.ini

  # Install flake8.
  pip install flake8

  # Lint with flake8.
  flake8 --config .github/linters/tox.ini

  # Install editorconfig-checker.
  pip install editorconfig-checker

  # Lint with editorconfig-checker.
  # PATH: Directory or file path of your changes.
  editorconfig-checker --config .editorconfig PATH

  ```

- [Update Change Log](https://github.com/github-changelog-generator/github-changelog-generator#installation) (if needed)
