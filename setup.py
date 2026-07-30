from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

with open("tg_alarm_requirements.txt") as f:
    install_requires = [l.strip() for l in f if l.strip() and not l.startswith("#")]

setup(
    name="tg-alarm",
    version="1.0.0",
    description="Telegram alarm - repeatedly calls a user until they reply",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="pefkez",
    url="https://github.com/pefkez/tg-alarm",
    packages=find_packages(include=["providers", "web", "src"]),
    py_modules=["bot", "scheduler", "group_alarm", "mqtt_bridge", "captcha_verifier"],
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "tg-alarm-bot=bot:main",
            "tg-alarm-dashboard=web.dashboard:start_dashboard",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)
