package main

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"
)

const HighUtilizationThreshold = 80.0

// sanitizeLogInput removes potentially dangerous characters from log inputs
func sanitizeLogInput(input string) string {
	// Remove newlines, carriage returns, and other control characters to prevent log injection
	re := regexp.MustCompile(`[\r\n\t\x00-\x1f\x7f-\x9f]`)
	return re.ReplaceAllString(input, "_")
}

// AriaClient represents a client for VMware Aria Suite APIs
type AriaClient struct {
	BaseURL    string
	Username   string
	Password   string
	AuthToken  string
	HTTPClient *http.Client
	Logger     *log.Logger
}

// AuthRequest represents authentication request payload
type AuthRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
	Domain   string `json:"domain,omitempty"`
}

// AuthResponse represents authentication response
type AuthResponse struct {
	Token        string `json:"token"`
	CSPAuthToken string `json:"cspAuthToken"`
	RefreshToken string `json:"refresh_token"`
	ExpiresIn    int    `json:"expiresIn"`
}

// Resource represents a vRealize Operations resource
type Resource struct {
	Identifier  string      `json:"identifier"`
	ResourceKey ResourceKey `json:"resourceKey"`
	CreationTime int64      `json:"creationTime"`
	ResourceStatusStates []ResourceStatusState `json:"resourceStatusStates"`
}

// ResourceKey represents resource identification
type ResourceKey struct {
	Name               string `json:"name"`
	AdapterKindKey     string `json:"adapterKindKey"`
	ResourceKindKey    string `json:"resourceKindKey"`
	ResourceIdentifiers []ResourceIdentifier `json:"resourceIdentifiers"`
}

// ResourceIdentifier represents resource identifier
type ResourceIdentifier struct {
	IdentifierType ResourceIdentifierType `json:"identifierType"`
	Value          string                 `json:"value"`
}

// ResourceIdentifierType represents identifier type
type ResourceIdentifierType struct {
	Name                string `json:"name"`
	DataType            string `json:"dataType"`
	IsPartOfUniqueness  bool   `json:"isPartOfUniqueness"`
}

// ResourceStatusState represents resource status
type ResourceStatusState struct {
	AdapterInstanceId string `json:"adapterInstanceId"`
	ResourceState     string `json:"resourceState"`
	ResourceStatus    string `json:"resourceStatus"`
}

// ResourcesResponse represents API response for resources
type ResourcesResponse struct {
	ResourceList []Resource `json:"resourceList"`
	PageInfo     PageInfo   `json:"pageInfo"`
}

// PageInfo represents pagination information
type PageInfo struct {
	TotalCount int `json:"totalCount"`
	Page       int `json:"page"`
	PageSize   int `json:"pageSize"`
}

// MetricData represents metric data point
type MetricData struct {
	ResourceID string    `json:"resourceId"`
	MetricKey  string    `json:"metricKey"`
	Timestamp  time.Time `json:"timestamp"`
	Value      float64   `json:"value"`
	Unit       string    `json:"unit"`
}

// StatsResponse represents stats API response
type StatsResponse struct {
	Values []StatValue `json:"values"`
}

// StatValue represents a stat value
type StatValue struct {
	StatKey StatKey     `json:"statKey"`
	Data    [][]float64 `json:"data"`
}

// StatKey represents stat key information
type StatKey struct {
	Key  string `json:"key"`
	Unit string `json:"unit"`
}

// Alert represents an alert
type Alert struct {
	AlertId          string `json:"alertId"`
	AlertDefinitionId string `json:"alertDefinitionId"`
	AlertLevel       string `json:"alertLevel"`
	Status           string `json:"status"`
	StartTimeUTC     int64  `json:"startTimeUTC"`
	UpdateTimeUTC    int64  `json:"updateTimeUTC"`
	Type             string `json:"type"`
	SubType          string `json:"subType"`
	ResourceId       string `json:"resourceId"`
}

// AlertsResponse represents alerts API response
type AlertsResponse struct {
	Alerts []Alert `json:"alerts"`
}

// Blueprint represents an Aria Automation blueprint
type Blueprint struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
	Content     string `json:"content"`
	ProjectId   string `json:"projectId"`
	Status      string `json:"status"`
	CreatedAt   string `json:"createdAt"`
	UpdatedAt   string `json:"updatedAt"`
}

// BlueprintsResponse represents blueprints API response
type BlueprintsResponse struct {
	Content          []Blueprint `json:"content"`
	TotalElements    int         `json:"totalElements"`
	NumberOfElements int         `json:"numberOfElements"`
}

// Deployment represents an Aria Automation deployment
type Deployment struct {
	ID           string                 `json:"id"`
	Name         string                 `json:"name"`
	Description  string                 `json:"description"`
	BlueprintId  string                 `json:"blueprintId"`
	ProjectId    string                 `json:"projectId"`
	Status       string                 `json:"status"`
	Inputs       map[string]interface{} `json:"inputs"`
	CreatedAt    string                 `json:"createdAt"`
	UpdatedAt    string                 `json:"updatedAt"`
}

// DeploymentsResponse represents deployments API response
type DeploymentsResponse struct {
	Content          []Deployment `json:"content"`
	TotalElements    int          `json:"totalElements"`
	NumberOfElements int          `json:"numberOfElements"`
}

// validateURL validates that the URL is safe and allowed
func validateURL(rawURL string) error {
	parsedURL, err := url.Parse(rawURL)
	if err != nil {
		return fmt.Errorf("invalid URL: %w", err)
	}
	
	// Only allow HTTPS
	if parsedURL.Scheme != "https" {
		return fmt.Errorf("only HTTPS URLs are allowed")
	}
	
	// Validate hostname (basic allowlist)
	allowedHosts := []string{
		"aria-ops.lab.local",
		"aria-auto.lab.local",
		"localhost",
	}
	
	for _, allowed := range allowedHosts {
		if parsedURL.Hostname() == allowed {
			return nil
		}
	}
	
	return fmt.Errorf("hostname not in allowlist: %s", parsedURL.Hostname())
}

// NewAriaClient creates a new Aria client
func NewAriaClient(baseURL, username, password string, skipSSLVerify bool) *AriaClient {
	tr := &http.Transport{
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify: skipSSLVerify,
			MinVersion:         tls.VersionTLS12, // Changed from TLS13 for compatibility
		},
	}
	
	client := &http.Client{
		Transport: tr,
		Timeout:   30 * time.Second,
	}
	
	// Validate the base URL
	if err := validateURL(baseURL); err != nil {
		log.Fatalf("Invalid base URL: %v", err)
	}
	
	return &AriaClient{
		BaseURL:    strings.TrimSuffix(baseURL, "/"),
		Username:   username,
		Password:   password,
		HTTPClient: client,
		Logger:     log.New(log.Writer(), "[AriaClient] ", log.LstdFlags),
	}
}

// Authenticate authenticates with Aria Operations
func (c *AriaClient) Authenticate() error {
	authURL := c.BaseURL + "/suite-api/api/auth/token/acquire"
	
	authReq := AuthRequest{
		Username: c.Username,
		Password: c.Password,
	}
	
	jsonData, err := json.Marshal(authReq)
	if err != nil {
		return fmt.Errorf("failed to marshal auth request: %w", err)
	}
	
	req, err := http.NewRequest("POST", authURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create auth request: %w", err)
	}
	
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	
	c.Logger.Printf("Authenticating with %s", sanitizeLogInput(authURL))
	
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return fmt.Errorf("authentication request failed: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("authentication failed with status %d: %s", resp.StatusCode, string(body))
	}
	
	var authResp AuthResponse
	if err := json.NewDecoder(resp.Body).Decode(&authResp); err != nil {
		return fmt.Errorf("failed to decode auth response: %w", err)
	}
	
	c.AuthToken = authResp.Token
	c.Logger.Printf("Authentication successful")
	
	return nil
}

// makeAuthenticatedRequest makes an authenticated HTTP request
func (c *AriaClient) makeAuthenticatedRequest(method, endpoint string, body io.Reader) (*http.Response, error) {
	if c.AuthToken == "" {
		if err := c.Authenticate(); err != nil {
			return nil, fmt.Errorf("authentication failed: %w", err)
		}
	}
	
	fullURL := c.BaseURL + endpoint
	
	// Validate the full URL before making request
	if err := validateURL(fullURL); err != nil {
		return nil, fmt.Errorf("invalid request URL: %w", err)
	}
	
	req, err := http.NewRequest(method, fullURL, body)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	
	req.Header.Set("Authorization", "vRealizeOpsToken "+c.AuthToken)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	
	// Handle token expiration
	if resp.StatusCode == http.StatusUnauthorized {
		resp.Body.Close()
		c.AuthToken = "" // Clear expired token
		if err := c.Authenticate(); err != nil {
			return nil, fmt.Errorf("re-authentication failed: %w", err)
		}
		
		// Retry request with new token
		req.Header.Set("Authorization", "vRealizeOpsToken "+c.AuthToken)
		return c.HTTPClient.Do(req)
	}
	
	return resp, nil
}

// GetResources retrieves resources from Aria Operations
func (c *AriaClient) GetResources(resourceKind string, pageSize int) ([]Resource, error) {
	endpoint := "/suite-api/api/resources"
	
	params := url.Values{}
	if resourceKind != "" {
		params.Add("resourceKind", resourceKind)
	}
	if pageSize > 0 {
		params.Add("pageSize", strconv.Itoa(pageSize))
	}
	
	if len(params) > 0 {
		endpoint += "?" + params.Encode()
	}
	
	c.Logger.Printf("Retrieving resources from %s", sanitizeLogInput(endpoint))
	
	resp, err := c.makeAuthenticatedRequest("GET", endpoint, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to get resources: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("get resources failed with status %d: %s", resp.StatusCode, string(body))
	}
	
	var resourcesResp ResourcesResponse
	if err := json.NewDecoder(resp.Body).Decode(&resourcesResp); err != nil {
		return nil, fmt.Errorf("failed to decode resources response: %w", err)
	}
	
	c.Logger.Printf("Retrieved %d resources", len(resourcesResp.ResourceList))
	return resourcesResp.ResourceList, nil
}

// GetMetrics retrieves metrics for a resource
func (c *AriaClient) GetMetrics(resourceID string, metricKeys []string, startTime, endTime time.Time) ([]MetricData, error) {
	endpoint := fmt.Sprintf("/suite-api/api/resources/%s/stats", resourceID)
	
	params := url.Values{}
	for _, key := range metricKeys {
		params.Add("statKey", key)
	}
	params.Add("begin", strconv.FormatInt(startTime.UnixNano()/1000000, 10))
	params.Add("end", strconv.FormatInt(endTime.UnixNano()/1000000, 10))
	params.Add("rollUpType", "AVG")
	params.Add("intervalType", "MINUTES")
	params.Add("intervalQuantifier", "5")
	
	endpoint += "?" + params.Encode()
	
	c.Logger.Printf("Retrieving metrics for resource %s", sanitizeLogInput(resourceID))
	
	resp, err := c.makeAuthenticatedRequest("GET", endpoint, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to get metrics: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("get metrics failed with status %d: %s", resp.StatusCode, string(body))
	}
	
	var statsResp StatsResponse
	if err := json.NewDecoder(resp.Body).Decode(&statsResp); err != nil {
		return nil, fmt.Errorf("failed to decode stats response: %w", err)
	}
	
	var metrics []MetricData
	for _, statValue := range statsResp.Values {
		for _, dataPoint := range statValue.Data {
			if len(dataPoint) >= 2 {
				timestamp := time.Unix(int64(dataPoint[0])/1000, 0)
				value := dataPoint[1]
				
				metrics = append(metrics, MetricData{
					ResourceID: resourceID,
					MetricKey:  statValue.StatKey.Key,
					Timestamp:  timestamp,
					Value:      value,
					Unit:       statValue.StatKey.Unit,
				})
			}
		}
	}
	
	c.Logger.Printf("Retrieved %d metric data points", len(metrics))
	return metrics, nil
}

// GetAlerts retrieves active alerts
func (c *AriaClient) GetAlerts(severity string) ([]Alert, error) {
	endpoint := "/suite-api/api/alerts"
	
	params := url.Values{}
	params.Add("activeOnly", "true")
	if severity != "" {
		params.Add("alertCriticality", severity)
	}
	
	endpoint += "?" + params.Encode()
	
	c.Logger.Printf("Retrieving alerts")
	
	resp, err := c.makeAuthenticatedRequest("GET", endpoint, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to get alerts: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("get alerts failed with status %d: %s", resp.StatusCode, string(body))
	}
	
	var alertsResp AlertsResponse
	if err := json.NewDecoder(resp.Body).Decode(&alertsResp); err != nil {
		return nil, fmt.Errorf("failed to decode alerts response: %w", err)
	}
	
	c.Logger.Printf("Retrieved %d alerts", len(alertsResp.Alerts))
	return alertsResp.Alerts, nil
}

// GenerateHealthReport generates a comprehensive health report
func (c *AriaClient) GenerateHealthReport(resourceKind string) (map[string]interface{}, error) {
	c.Logger.Printf("Generating health report for %s", resourceKind)
	
	// Get resources
	resources, err := c.GetResources(resourceKind, 50)
	if err != nil {
		return nil, fmt.Errorf("failed to get resources: %w", err)
	}
	
	if len(resources) == 0 {
		return map[string]interface{}{
			"error": "No resources found",
		}, nil
	}
	
	// Define key metrics
	keyMetrics := []string{
		"cpu|usage_average",
		"mem|usage_average",
		"disk|usage_average",
		"net|usage_average",
	}
	
	// Collect metrics for first 10 resources (for performance)
	var allMetrics []MetricData
	endTime := time.Now()
	startTime := endTime.Add(-1 * time.Hour)
	
	resourceCount := len(resources)
	if resourceCount > 10 {
		resourceCount = 10
	}
	
	for i := 0; i < resourceCount; i++ {
		resource := resources[i]
		metrics, err := c.GetMetrics(resource.Identifier, keyMetrics, startTime, endTime)
		if err != nil {
			c.Logger.Printf("Failed to get metrics for resource %s: %v", resource.Identifier, err)
			continue
		}
		allMetrics = append(allMetrics, metrics...)
	}
	
	// Get active alerts
	alerts, err := c.GetAlerts("")
	if err != nil {
		c.Logger.Printf("Failed to get alerts: %v", err)
		alerts = []Alert{} // Continue with empty alerts
	}
	
	// Analyze metrics
	metricsSummary := c.analyzeMetrics(allMetrics)
	
	// Generate recommendations
	recommendations := c.generateRecommendations(allMetrics, alerts)
	
	// Build report
	report := map[string]interface{}{
		"generatedAt":        time.Now().Format(time.RFC3339),
		"resourceKind":       resourceKind,
		"totalResources":     len(resources),
		"resourcesAnalyzed":  resourceCount,
		"activeAlerts":       len(alerts),
		"metricsSummary":     metricsSummary,
		"topAlerts":          alerts[:min(len(alerts), 5)],
		"recommendations":    recommendations,
	}
	
	c.Logger.Printf("Health report generated successfully")
	return report, nil
}

// analyzeMetrics analyzes collected metrics
func (c *AriaClient) analyzeMetrics(metrics []MetricData) map[string]interface{} {
	summary := map[string]interface{}{
		"cpuUtilization": map[string]interface{}{
			"avg": 0.0, "max": 0.0, "resourcesOver80": 0,
		},
		"memoryUtilization": map[string]interface{}{
			"avg": 0.0, "max": 0.0, "resourcesOver80": 0,
		},
		"diskUtilization": map[string]interface{}{
			"avg": 0.0, "max": 0.0, "resourcesOver80": 0,
		},
	}
	
	var cpuValues, memValues, diskValues []float64
	
	for _, metric := range metrics {
		switch {
		case strings.Contains(metric.MetricKey, "cpu|usage"):
			cpuValues = append(cpuValues, metric.Value)
		case strings.Contains(metric.MetricKey, "mem|usage"):
			memValues = append(memValues, metric.Value)
		case strings.Contains(metric.MetricKey, "disk|usage"):
			diskValues = append(diskValues, metric.Value)
		}
	}
	
	// Calculate CPU statistics
	if len(cpuValues) > 0 {
		avg, max, over80 := calculateStats(cpuValues)
		summary["cpuUtilization"] = map[string]interface{}{
			"avg": avg, "max": max, "resourcesOver80": over80,
		}
	}
	
	// Calculate Memory statistics
	if len(memValues) > 0 {
		avg, max, over80 := calculateStats(memValues)
		summary["memoryUtilization"] = map[string]interface{}{
			"avg": avg, "max": max, "resourcesOver80": over80,
		}
	}
	
	// Calculate Disk statistics
	if len(diskValues) > 0 {
		avg, max, over80 := calculateStats(diskValues)
		summary["diskUtilization"] = map[string]interface{}{
			"avg": avg, "max": max, "resourcesOver80": over80,
		}
	}
	
	return summary
}

// calculateStats calculates statistics for a slice of values
func calculateStats(values []float64) (avg, max float64, over80 int) {
	if len(values) == 0 {
		return 0, 0, 0
	}
	
	sum := 0.0
	max = values[0]
	
	for _, value := range values {
		sum += value
		if value > max {
			max = value
		}
		if value > HighUtilizationThreshold {
			over80++
		}
	}
	
	avg = sum / float64(len(values))
	return avg, max, over80
}

// generateRecommendations generates actionable recommendations
func (c *AriaClient) generateRecommendations(metrics []MetricData, alerts []Alert) []string {
	var recommendations []string
	
	// Analyze high resource utilization
	highCPUCount := 0
	highMemCount := 0
	
	for _, metric := range metrics {
		if strings.Contains(metric.MetricKey, "cpu|usage") && metric.Value > HighUtilizationThreshold {
			highCPUCount++
		}
		if strings.Contains(metric.MetricKey, "mem|usage") && metric.Value > HighUtilizationThreshold {
			highMemCount++
		}
	}
	
	if highCPUCount > 0 {
		recommendations = append(recommendations,
			fmt.Sprintf("Consider CPU optimization for %d resources with high utilization", highCPUCount))
	}
	
	if highMemCount > 0 {
		recommendations = append(recommendations,
			fmt.Sprintf("Review memory allocation for %d resources", highMemCount))
	}
	
	// Analyze alerts
	criticalAlerts := 0
	for _, alert := range alerts {
		if alert.AlertLevel == "CRITICAL" {
			criticalAlerts++
		}
	}
	
	if criticalAlerts > 0 {
		recommendations = append(recommendations,
			fmt.Sprintf("Immediate attention required for %d critical alerts", criticalAlerts))
	}
	
	if len(recommendations) == 0 {
		recommendations = append(recommendations, "System appears to be operating within normal parameters")
	}
	
	return recommendations
}

// min returns the minimum of two integers
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// ExportReport exports report to JSON file
func (c *AriaClient) ExportReport(report map[string]interface{}, filename string) error {
	jsonData, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal report: %w", err)
	}
	
	// In a real implementation, you would write to file
	// For this example, we'll just log the size
	c.Logger.Printf("Report exported (%d bytes) - would write to %s", len(jsonData), sanitizeLogInput(filename))
	
	return nil
}

// Example usage
func main() {
	// Get credentials from environment variables
	hostname := os.Getenv("ARIA_HOSTNAME")
	username := os.Getenv("ARIA_USERNAME")
	password := os.Getenv("ARIA_PASSWORD")
	
	if hostname == "" {
		hostname = "https://aria-ops.lab.local"
	}
	if username == "" {
		username = os.Getenv("ARIA_DEFAULT_USER")
		if username == "" {
			log.Fatal("ARIA_USERNAME or ARIA_DEFAULT_USER environment variable must be set")
		}
	}
	if password == "" {
		log.Fatal("ARIA_PASSWORD environment variable must be set")
	}
	
	// Initialize client
	client := NewAriaClient(
		hostname,
		username,
		password,
		true, // Skip SSL verification for lab
	)
	
	// Generate health report
	report, err := client.GenerateHealthReport("VirtualMachine")
	if err != nil {
		log.Fatalf("Failed to generate health report: %v", err)
	}
	
	// Export report
	timestamp := time.Now().Format("20060102_150405")
	filename := fmt.Sprintf("aria_health_report_%s.json", timestamp)
	
	if err := client.ExportReport(report, filename); err != nil {
		log.Fatalf("Failed to export report: %v", err)
	}
	
	fmt.Printf("Health report generated successfully!\n")
	fmt.Printf("Total Resources: %v\n", report["totalResources"])
	fmt.Printf("Active Alerts: %v\n", report["activeAlerts"])
	fmt.Printf("Recommendations: %v\n", len(report["recommendations"].([]string)))
}# Updated Sun Nov  9 12:50:01 CET 2025
# Updated Sun Nov  9 12:52:21 CET 2025
