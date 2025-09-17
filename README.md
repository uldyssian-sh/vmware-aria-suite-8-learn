# VMware Infrastructure Automation

[![CI](https://github.com/uldyssian-sh/vmware-aria-suite-8-learn/workflows/CI/badge.svg)](https://github.com/uldyssian-sh/vmware-aria-suite-8-learn/actions)
[![Security](https://github.com/uldyssian-sh/vmware-aria-suite-8-learn/workflows/Security/badge.svg)](https://github.com/uldyssian-sh/vmware-aria-suite-8-learn/security)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Professional VMware infrastructure automation and compliance tools for enterprise environments.

## Features

- ✅ **Automated Compliance**: STIG/CIS compliance checks
- 🔒 **Security Hardening**: Enterprise security standards  
- 📊 **Health Monitoring**: Real-time infrastructure monitoring
- 🚀 **CI/CD Integration**: Automated deployment pipelines
- 📚 **Documentation**: Comprehensive guides and examples

## Quick Start

```bash
# Clone repository
git clone https://github.com/uldyssian-sh/vmware-aria-suite-8-learn.git
cd vmware-aria-suite-8-learn

# Install dependencies
pip install -r requirements.txt

# Run compliance check
python main.py --check-compliance
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   vCenter       │────│   ESXi Hosts    │────│   Virtual VMs   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Monitoring    │
                    └─────────────────┘
```

## Documentation

- [Installation Guide](https://github.com/uldyssian-sh/vmware-aria-suite-8-learn/wiki/Installation)
- [Configuration](https://github.com/uldyssian-sh/vmware-aria-suite-8-learn/wiki/Configuration)
- [API Reference](https://github.com/uldyssian-sh/vmware-aria-suite-8-learn/wiki/API)
- [Troubleshooting](https://github.com/uldyssian-sh/vmware-aria-suite-8-learn/wiki/Troubleshooting)

## Security

- [Security Policy](SECURITY.md)
- [Vulnerability Reporting](SECURITY.md#reporting-a-vulnerability)

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 💬 Discussions: [GitHub Discussions](https://github.com/uldyssian-sh/vmware-aria-suite-8-learn/discussions)
- 🐛 Issues: [GitHub Issues](https://github.com/uldyssian-sh/vmware-aria-suite-8-learn/issues)
- 📖 Wiki: [Documentation Wiki](https://github.com/uldyssian-sh/vmware-aria-suite-8-learn/wiki)
