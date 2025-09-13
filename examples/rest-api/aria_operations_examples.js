/**
 * VMware Aria Operations REST API Examples
 * Comprehensive JavaScript/Node.js examples for Aria Operations integration
 */

const https = require('https');
const axios = require('axios');
const fs = require('fs').promises;
const path = require('path');

class AriaOperationsClient {
    constructor(config) {
        this.baseUrl = `https://${config.hostname}:${config.port || 443}`;
        this.credentials = config.credentials;
        this.authToken = null;
        this.tokenExpiry = null;
        
        // Configure axios with SSL settings
        this.client = axios.create({
            baseURL: this.baseUrl,
            timeout: 30000,
            httpsAgent: new https.Agent({
                rejectUnauthorized: config.verifySSL || false
            }),
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        });
        
        // Add request interceptor for token refresh
        this.client.interceptors.request.use(async (config) => {
            if (this.isTokenExpired()) {
                await this.authenticate();
            }
            if (this.authToken) {
                config.headers.Authorization = `vRealizeOpsToken ${this.authToken}`;
            }
            return config;
        });
        
        // Add response interceptor for error handling
        this.client.interceptors.response.use(
            response => response,
            error => {
                console.error(`API Error: ${error.response?.status} - ${error.response?.statusText}`);
                return Promise.reject(error);
            }
        );
    }
    
    async authenticate() {
        try {
            console.log('Authenticating with Aria Operations...');
            
            const response = await this.client.post('/suite-api/api/auth/token/acquire', {
                username: this.credentials.username,
                password: this.credentials.password
            });
            
            this.authToken = response.data.token;
            this.tokenExpiry = new Date(Date.now() + (response.data.validity * 1000));
            
            console.log('✓ Authentication successful');
            return true;
        } catch (error) {
            console.error('✗ Authentication failed:', error.message);
            throw error;
        }
    }
    
    isTokenExpired() {
        return !this.authToken || !this.tokenExpiry || new Date() >= this.tokenExpiry;
    }
    
    async getResources(filters = {}) {
        try {
            const params = new URLSearchParams();
            
            if (filters.resourceKind) params.append('resourceKind', filters.resourceKind);
            if (filters.name) params.append('name', filters.name);
            if (filters.pageSize) params.append('pageSize', filters.pageSize);
            
            const response = await this.client.get(`/suite-api/api/resources?${params}`);
            
            console.log(`✓ Retrieved ${response.data.resourceList?.length || 0} resources`);
            return response.data.resourceList || [];
        } catch (error) {
            console.error('✗ Failed to retrieve resources:', error.message);
            throw error;
        }
    }
    
    async getMetrics(resourceId, metricKeys, timeRange = {}) {
        try {
            const endTime = timeRange.end || Date.now();
            const startTime = timeRange.start || (endTime - (60 * 60 * 1000)); // 1 hour ago
            
            const params = new URLSearchParams();
            metricKeys.forEach(key => params.append('statKey', key));
            params.append('begin', startTime);
            params.append('end', endTime);
            params.append('rollUpType', 'AVG');
            params.append('intervalType', 'MINUTES');
            params.append('intervalQuantifier', '5');
            
            const response = await this.client.get(
                `/suite-api/api/resources/${resourceId}/stats?${params}`
            );
            
            const metrics = this.parseMetricsResponse(response.data, resourceId);
            console.log(`✓ Retrieved ${metrics.length} metric data points`);
            return metrics;
        } catch (error) {
            console.error('✗ Failed to retrieve metrics:', error.message);
            throw error;
        }
    }
    
    parseMetricsResponse(data, resourceId) {
        const metrics = [];
        
        if (data.values) {
            data.values.forEach(stat => {
                const metricKey = stat.statKey?.key || '';
                if (stat.data) {
                    stat.data.forEach(([timestamp, value]) => {
                        metrics.push({
                            resourceId,
                            metricKey,
                            timestamp: new Date(timestamp),
                            value: parseFloat(value),
                            unit: stat.statKey?.unit || ''
                        });
                    });
                }
            });
        }
        
        return metrics;
    }
    
    async getAlerts(filters = {}) {
        try {
            const params = new URLSearchParams();
            params.append('activeOnly', 'true');
            
            if (filters.severity) params.append('alertCriticality', filters.severity);
            if (filters.resourceKind) params.append('resourceKind', filters.resourceKind);
            
            const response = await this.client.get(`/suite-api/api/alerts?${params}`);
            
            console.log(`✓ Retrieved ${response.data.alerts?.length || 0} alerts`);
            return response.data.alerts || [];
        } catch (error) {
            console.error('✗ Failed to retrieve alerts:', error.message);
            throw error;
        }
    }
    
    async createCustomGroup(groupDefinition) {
        try {
            const response = await this.client.post('/suite-api/api/resources/groups', groupDefinition);
            
            console.log(`✓ Created custom group: ${groupDefinition.resourceKey.name}`);
            return response.data;
        } catch (error) {
            console.error('✗ Failed to create custom group:', error.message);
            throw error;
        }
    }
    
    async generateHealthReport(resourceKind = 'VirtualMachine') {
        try {
            console.log(`Generating health report for ${resourceKind}...`);
            
            // Get resources
            const resources = await this.getResources({ 
                resourceKind, 
                pageSize: 50 
            });
            
            if (resources.length === 0) {
                return { error: 'No resources found' };
            }
            
            // Define key metrics
            const keyMetrics = [
                'cpu|usage_average',
                'mem|usage_average',
                'disk|usage_average',
                'net|usage_average'
            ];
            
            // Collect metrics for resources (limit for performance)
            const metricsPromises = resources.slice(0, 10).map(resource => 
                this.getMetrics(resource.identifier, keyMetrics)
                    .catch(error => {
                        console.warn(`Failed to get metrics for ${resource.identifier}:`, error.message);
                        return [];
                    })
            );
            
            const metricsResults = await Promise.all(metricsPromises);
            const allMetrics = metricsResults.flat();
            
            // Get active alerts
            const alerts = await this.getAlerts({ resourceKind });
            
            // Generate report
            const report = {
                generatedAt: new Date().toISOString(),
                resourceKind,
                totalResources: resources.length,
                resourcesAnalyzed: Math.min(resources.length, 10),
                activeAlerts: alerts.length,
                metricsSummary: this.analyzeMetrics(allMetrics),
                topAlerts: alerts.slice(0, 5),
                recommendations: this.generateRecommendations(allMetrics, alerts),
                resourceDetails: resources.slice(0, 10).map(r => ({
                    name: r.resourceKey?.name,
                    identifier: r.identifier,
                    resourceKind: r.resourceKey?.resourceKindKey,
                    adapterKind: r.resourceKey?.adapterKindKey
                }))
            };
            
            console.log('✓ Health report generated successfully');
            return report;
        } catch (error) {
            console.error('✗ Failed to generate health report:', error.message);
            throw error;
        }
    }
    
    analyzeMetrics(metrics) {
        const summary = {
            cpuUtilization: { avg: 0, max: 0, resourcesOver80: 0 },
            memoryUtilization: { avg: 0, max: 0, resourcesOver80: 0 },
            diskUtilization: { avg: 0, max: 0, resourcesOver80: 0 },
            networkUtilization: { avg: 0, max: 0, resourcesOver80: 0 }
        };
        
        const cpuValues = metrics.filter(m => m.metricKey.includes('cpu|usage')).map(m => m.value);
        const memValues = metrics.filter(m => m.metricKey.includes('mem|usage')).map(m => m.value);
        const diskValues = metrics.filter(m => m.metricKey.includes('disk|usage')).map(m => m.value);
        const netValues = metrics.filter(m => m.metricKey.includes('net|usage')).map(m => m.value);
        
        if (cpuValues.length > 0) {
            summary.cpuUtilization.avg = cpuValues.reduce((a, b) => a + b, 0) / cpuValues.length;
            summary.cpuUtilization.max = Math.max(...cpuValues);
            summary.cpuUtilization.resourcesOver80 = cpuValues.filter(v => v > 80).length;
        }
        
        if (memValues.length > 0) {
            summary.memoryUtilization.avg = memValues.reduce((a, b) => a + b, 0) / memValues.length;
            summary.memoryUtilization.max = Math.max(...memValues);
            summary.memoryUtilization.resourcesOver80 = memValues.filter(v => v > 80).length;
        }
        
        if (diskValues.length > 0) {
            summary.diskUtilization.avg = diskValues.reduce((a, b) => a + b, 0) / diskValues.length;
            summary.diskUtilization.max = Math.max(...diskValues);
            summary.diskUtilization.resourcesOver80 = diskValues.filter(v => v > 80).length;
        }
        
        if (netValues.length > 0) {
            summary.networkUtilization.avg = netValues.reduce((a, b) => a + b, 0) / netValues.length;
            summary.networkUtilization.max = Math.max(...netValues);
            summary.networkUtilization.resourcesOver80 = netValues.filter(v => v > 80).length;
        }
        
        return summary;
    }
    
    generateRecommendations(metrics, alerts) {
        const recommendations = [];
        
        // Analyze high utilization
        const highCpuMetrics = metrics.filter(m => m.metricKey.includes('cpu|usage') && m.value > 80);
        const highMemMetrics = metrics.filter(m => m.metricKey.includes('mem|usage') && m.value > 80);
        
        if (highCpuMetrics.length > 0) {
            recommendations.push(`Consider CPU optimization for ${highCpuMetrics.length} high utilization instances`);
        }
        
        if (highMemMetrics.length > 0) {
            recommendations.push(`Review memory allocation for ${highMemMetrics.length} resources`);
        }
        
        // Analyze alerts
        const criticalAlerts = alerts.filter(a => a.alertLevel === 'CRITICAL');
        if (criticalAlerts.length > 0) {
            recommendations.push(`Immediate attention required for ${criticalAlerts.length} critical alerts`);
        }
        
        if (recommendations.length === 0) {
            recommendations.push('System appears to be operating within normal parameters');
        }
        
        return recommendations;
    }
    
    async exportReport(report, filename) {
        try {
            const filePath = path.resolve(filename);
            await fs.writeFile(filePath, JSON.stringify(report, null, 2), 'utf8');
            console.log(`✓ Report exported to: ${filePath}`);
            return filePath;
        } catch (error) {
            console.error('✗ Failed to export report:', error.message);
            throw error;
        }
    }
}

// Utility functions for common operations
class AriaOperationsUtils {
    static async bulkMetricsCollection(client, resourceIds, metricKeys, concurrency = 5) {
        const results = {};
        const chunks = this.chunkArray(resourceIds, concurrency);
        
        for (const chunk of chunks) {
            const promises = chunk.map(async resourceId => {
                try {
                    const metrics = await client.getMetrics(resourceId, metricKeys);
                    return { resourceId, metrics };
                } catch (error) {
                    console.warn(`Failed to collect metrics for ${resourceId}:`, error.message);
                    return { resourceId, metrics: [] };
                }
            });
            
            const chunkResults = await Promise.all(promises);
            chunkResults.forEach(({ resourceId, metrics }) => {
                results[resourceId] = metrics;
            });
        }
        
        return results;
    }
    
    static chunkArray(array, chunkSize) {
        const chunks = [];
        for (let i = 0; i < array.length; i += chunkSize) {
            chunks.push(array.slice(i, i + chunkSize));
        }
        return chunks;
    }
    
    static formatMetricsForChart(metrics, metricKey) {
        return metrics
            .filter(m => m.metricKey === metricKey)
            .sort((a, b) => a.timestamp - b.timestamp)
            .map(m => ({
                x: m.timestamp.toISOString(),
                y: m.value
            }));
    }
    
    static calculatePercentile(values, percentile) {
        const sorted = values.sort((a, b) => a - b);
        const index = Math.ceil((percentile / 100) * sorted.length) - 1;
        return sorted[index];
    }
}

// Example usage and demonstrations
async function demonstrateAriaOperationsAPI() {
    const config = {
        hostname: 'aria-ops.lab.local',
        port: 443,
        verifySSL: false,
        credentials: {
            username: 'admin',
            password: 'VMware123!'
        }
    };
    
    const client = new AriaOperationsClient(config);
    
    try {
        // Authenticate
        await client.authenticate();
        
        // Generate comprehensive health report
        const report = await client.generateHealthReport('VirtualMachine');
        
        // Export report with timestamp
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `aria-health-report-${timestamp}.json`;
        await client.exportReport(report, filename);
        
        // Display summary
        console.log('\n=== Health Report Summary ===');
        console.log(`Resources Analyzed: ${report.resourcesAnalyzed}`);
        console.log(`Active Alerts: ${report.activeAlerts}`);
        console.log(`CPU Avg: ${report.metricsSummary.cpuUtilization.avg.toFixed(2)}%`);
        console.log(`Memory Avg: ${report.metricsSummary.memoryUtilization.avg.toFixed(2)}%`);
        console.log('\nRecommendations:');
        report.recommendations.forEach((rec, index) => {
            console.log(`${index + 1}. ${rec}`);
        });
        
        return report;
    } catch (error) {
        console.error('Demonstration failed:', error.message);
        throw error;
    }
}

// Advanced monitoring example
async function setupAdvancedMonitoring() {
    const config = {
        hostname: process.env.ARIA_OPS_HOST || 'aria-ops.lab.local',
        credentials: {
            username: process.env.ARIA_OPS_USER || 'admin',
            password: process.env.ARIA_OPS_PASS || 'VMware123!'
        }
    };
    
    const client = new AriaOperationsClient(config);
    
    try {
        await client.authenticate();
        
        // Get all VM resources
        const vms = await client.getResources({ resourceKind: 'VirtualMachine' });
        console.log(`Found ${vms.length} virtual machines`);
        
        // Bulk collect metrics for performance analysis
        const vmIds = vms.slice(0, 20).map(vm => vm.identifier);
        const performanceMetrics = [
            'cpu|usage_average',
            'mem|usage_average',
            'disk|usage_average',
            'net|usage_average'
        ];
        
        console.log('Collecting performance metrics...');
        const metricsData = await AriaOperationsUtils.bulkMetricsCollection(
            client, vmIds, performanceMetrics, 3
        );
        
        // Analyze performance trends
        const analysis = {
            timestamp: new Date().toISOString(),
            totalVMs: vms.length,
            analyzedVMs: vmIds.length,
            performanceAnalysis: {}
        };
        
        performanceMetrics.forEach(metricKey => {
            const allValues = Object.values(metricsData)
                .flat()
                .filter(m => m.metricKey === metricKey)
                .map(m => m.value);
            
            if (allValues.length > 0) {
                analysis.performanceAnalysis[metricKey] = {
                    average: allValues.reduce((a, b) => a + b, 0) / allValues.length,
                    min: Math.min(...allValues),
                    max: Math.max(...allValues),
                    p95: AriaOperationsUtils.calculatePercentile(allValues, 95),
                    p99: AriaOperationsUtils.calculatePercentile(allValues, 99)
                };
            }
        });
        
        // Export detailed analysis
        const filename = `performance-analysis-${Date.now()}.json`;
        await client.exportReport(analysis, filename);
        
        console.log('\n=== Performance Analysis Complete ===');
        console.log(`Analysis exported to: ${filename}`);
        
        return analysis;
    } catch (error) {
        console.error('Advanced monitoring setup failed:', error.message);
        throw error;
    }
}

// Export for use as module
module.exports = {
    AriaOperationsClient,
    AriaOperationsUtils,
    demonstrateAriaOperationsAPI,
    setupAdvancedMonitoring
};

// Run demonstration if called directly
if (require.main === module) {
    demonstrateAriaOperationsAPI()
        .then(() => console.log('\n✓ Demonstration completed successfully'))
        .catch(error => {
            console.error('\n✗ Demonstration failed:', error.message);
            process.exit(1);
        });
}