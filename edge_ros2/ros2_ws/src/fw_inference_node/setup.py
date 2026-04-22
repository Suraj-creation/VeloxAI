from setuptools import find_packages, setup

package_name = 'fw_inference_node'

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
    description='Footwatch Stage 1 inference node — YOLOv8 two-wheeler detection',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'inference_node = fw_inference_node.inference_node:main',
        ],
    },
)
