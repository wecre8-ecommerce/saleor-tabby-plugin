from setuptools import setup

setup(
    name="tabby-payment-gateway",
    version="0.1.0",
    packages=["tabby"],
    package_dir={"tabby": "tabby"},
    description="Tappy payment plugin",
    entry_points={
        "saleor.plugins": ["tabby = tabby.plugin:TabbyGatewayPlugin"],
    },
)
