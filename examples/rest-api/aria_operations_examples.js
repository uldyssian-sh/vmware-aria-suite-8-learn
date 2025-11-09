/**
 * VMware Aria Operations REST API Examples
 * Simple JavaScript/Node.js examples for Aria Operations integration
 */

const https = require('https');
const fs = require('fs').promises;
const path = require('path');

class AriaOperationsClient {
    constructor(config) {
        this.baseUrl = `https://${config.hostname}:${config.port || 443}`;
        this.credentials = config.credentials;
        this.authToken = null;
        
        // Configure HTTPS agent for self-signed certificates
        this.httpsAgent = new https.Agent({
            rejectUnauthorized: config.verifySSL || false
        });
    }
    
    async authenticate() {
        try {
            console.log('Authenticating with Aria Operations...');
            
            const authData = JSON.stringify({
                username: this.credentials.username,
                password: this.credentials.password
            });
            
            const options = {
                hostname: new URL(this.baseUrl).hostname,
                port: new URL(this.baseUrl).port || 443,
                path: '/suite-api/api/auth/token/acquire',
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(authData)
                },
                agent: this.httpsAgent
            };
            
            const response = await this.makeRequest(options, authData);
            const result = JSON.parse(response);
            
            this.authToken = result.token;
            console.log('✓ Authentication successful');
            return true;
        } catch (error) {
            console.error('✗ Authentication failed:', error.message);
            throw error;
        }
    }
    
    async makeRequest(options, data = null) {
        return new Promise((resolve, reject) => {
            const req = https.request(options, (res) => {
                let responseData = '';
                
                res.on('data', (chunk) => {
                    responseData += chunk;
                });
                
                res.on('end', () => {
                    if (res.statusCode >= 200 && res.statusCode < 300) {
                        resolve(responseData);
                    } else {
                        reject(new Error(`HTTP ${res.statusCode}: ${responseData}`));
                    }
                });
            });
            
            req.on('error', (error) => {
                reject(error);
            });
            
            if (data) {
                req.write(data);
            }
            
            req.end();
        });
    }
    
    async getResources(resourceKind = null) {
        try {
            if (!this.authToken) {
                await this.authenticate();
            }
            
            let path = '/suite-api/api/resources';
            if (resourceKind) {
                path += `?resourceKind=${resourceKind}`;
            }
            
            const options = {
                hostname: new URL(this.baseUrl).hostname,
                port: new URL(this.baseUrl).port || 443,
                path: path,
                method: 'GET',
                headers: {
                    'Authorization': `vRealizeOpsToken ${this.authToken}`,
                    'Accept': 'application/json'
                },
                agent: this.httpsAgent
            };
            
            const response = await this.makeRequest(options);
            const result = JSON.parse(response);
            
            console.log(`✓ Retrieved ${result.resourceList?.length || 0} resources`);
            return result.resourceList || [];
        } catch (error) {
            console.error('✗ Failed to retrieve resources:', error.message);
            throw error;
        }
    }
    
    async getAlerts() {
        try {
            if (!this.authToken) {
                await this.authenticate();
            }
            
            const options = {
                hostname: new URL(this.baseUrl).hostname,
                port: new URL(this.baseUrl).port || 443,
                path: '/suite-api/api/alerts?activeOnly=true',
                method: 'GET',
                headers: {
                    'Authorization': `vRealizeOpsToken ${this.authToken}`,
                    'Accept': 'application/json'
                },
                agent: this.httpsAgent
            };
            
            const response = await this.makeRequest(options);
            const result = JSON.parse(response);
            
            console.log(`✓ Retrieved ${result.alerts?.length || 0} alerts`);
            return result.alerts || [];
        } catch (error) {
            console.error('✗ Failed to retrieve alerts:', error.message);
            throw error;
        }
    }
    
    async generateHealthReport() {
        try {
            console.log('Generating health report...');
            
            // Get resources
            const resources = await this.getResources('VirtualMachine');
            
            // Get active alerts
            const alerts = await this.getAlerts();
            
            // Generate report
            const report = {
                generatedAt: new Date().toISOString(),
                totalResources: resources.length,
                activeAlerts: alerts.length,
                status: alerts.length === 0 ? 'healthy' : 'warning',
                resourceSample: resources.slice(0, 5).map(r => ({
                    name: r.resourceKey?.name,
                    identifier: r.identifier
                }))
            };
            
            console.log('✓ Health report generated successfully');
            return report;
        } catch (error) {
            console.error('✗ Failed to generate health report:', error.message);
            throw error;
        }
    }
    
    _safePath(userPath) {
        // Sanitize filename and ensure it's in current directory
        const safeName = path.basename(userPath).replace(/[^a-zA-Z0-9.-]/g, '_');
        const safePath = path.join(process.cwd(), safeName);
        
        // Ensure the resolved path is within current directory
        const resolvedPath = path.resolve(safePath);
        const currentDir = path.resolve(process.cwd());
        
        if (!resolvedPath.startsWith(currentDir)) {
            throw new Error('Invalid file path: must be within current directory');
        }
        
        return resolvedPath;
    }
    
    async exportReport(report, filename) {
        try {
            const safePath = this._safePath(filename);
            await fs.writeFile(safePath, JSON.stringify(report, null, 2), 'utf8');
            console.log(`✓ Report exported to: ${safePath}`);
            return safePath;
        } catch (error) {
            console.error('✗ Failed to export report:', error.message);
            throw error;
        }
    }
}

// Example usage
async function demonstrateAriaOperationsAPI() {
    const config = {
        hostname: process.env.ARIA_HOSTNAME || 'aria-ops.lab.local',
        port: process.env.ARIA_PORT || 443,
        verifySSL: process.env.NODE_ENV === 'production',
        credentials: {
            username: process.env.ARIA_USERNAME || 'admin',
            password: process.env.ARIA_PASSWORD || (() => {
                throw new Error('ARIA_PASSWORD environment variable must be set');
            })()
        }
    };
    
    const client = new AriaOperationsClient(config);
    
    try {
        // Generate comprehensive health report
        const report = await client.generateHealthReport();
        
        // Export report with timestamp
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `aria-health-report-${timestamp}.json`;
        await client.exportReport(report, filename);
        
        // Display summary
        console.log('\n=== Health Report Summary ===');
        console.log(`Resources: ${report.totalResources}`);
        console.log(`Active Alerts: ${report.activeAlerts}`);
        console.log(`Status: ${report.status}`);
        
        return report;
    } catch (error) {
        console.error('Demonstration failed:', error.message);
        throw error;
    }
}

// Export for use as module
module.exports = {
    AriaOperationsClient,
    demonstrateAriaOperationsAPI
};

// Run demonstration if called directly
if (require.main === module) {
    demonstrateAriaOperationsAPI()
        .then(() => console.log('\n✓ Demonstration completed successfully'))
        .catch(error => {
            console.error('\n✗ Demonstration failed:', error.message);
            process.exit(1);
        });
}# Updated Sun Nov  9 12:50:01 CET 2025
