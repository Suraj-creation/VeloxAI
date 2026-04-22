from setuptools import find_packages, setup

package_name = 'fw_sensor_bridge'

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
    description='Footwatch camera ingress bridge — sole camera owner, '
                'publishes /fw/camera/frame CompressedImage with UUID frame_id',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'sensor_bridge_node = fw_sensor_bridge.sensor_bridge_node:main',
        ],
    },
)
