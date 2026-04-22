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
    install_requires=[
        'setuptools',
        'paho-mqtt>=1.6.1',
        'requests>=2.31.0',
    ],
    zip_safe=True,
    maintainer='Footwatch Edge Team',
    maintainer_email='footwatch@example.com',
    description='Footwatch cloud bridge with AWS IoT TLS, backend ingest mirroring, and durable delivery spool',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'mqtt_bridge_node = fw_ros2_mqtt_bridge.mqtt_bridge_node:main',
        ],
    },
)
