from setuptools import find_packages, setup

package_name = 'fw_violation_aggregator'

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
    description='Footwatch Stage 7 violation aggregator — evidence + challan generation',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'violation_aggregator = fw_violation_aggregator.violation_aggregator:main',
        ],
    },
)
