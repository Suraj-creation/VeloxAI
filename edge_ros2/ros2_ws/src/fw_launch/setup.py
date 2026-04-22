from setuptools import setup
import os
from glob import glob

package_name = 'fw_launch'

setup(
    name=package_name,
    version='1.0.0',
    packages=[],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
         glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Footwatch Edge Team',
    maintainer_email='footwatch@example.com',
    description='Launch file package for all Footwatch edge nodes',
    license='Apache-2.0',
)
