from setuptools import find_packages, setup

package_name = 'fw_plate_ocr_node'

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
    description='Footwatch Stages 4/5/6 plate localisation, enhancement and OCR node',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'plate_ocr_node = fw_plate_ocr_node.plate_ocr_node:main',
        ],
    },
)
