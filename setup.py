from setuptools import setup, find_packages

setup(
    name='k8s_tail',
    version='1.2.0',
    packages=find_packages(include=[
        'k8s_tail', 'k8s_tail.*'
    ]),
    python_requires='>=3',
    url='',
    license='',
    author='Tim Martin',
    author_email='timothy.martin@netapp.com',
    description='Kubernetes Script to tail container logs',
    install_requires=[
        'pyyaml'
    ],
    entry_points={
        'console_scripts': [
            'k8s-tail=k8s_tail.main:main'
        ]
    }
)
