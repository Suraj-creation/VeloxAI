from setuptools import find_packages, setup

package_name = 'fw_ros2_mqtt_bridge'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Footwatch Edge Team',
    maintainer_email='footwatch@example.com',
    description='Footwatch ROS2-to-MQTT bridge with SQLite spool and AWS IoT Core TLS',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'mqtt_bridge_node = fw_ros2_mqtt_bridge.mqtt_bridge_node:main',
        ],
    },
)
