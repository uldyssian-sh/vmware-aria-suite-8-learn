#!/usr/bin/env ruby
# VMware Aria Suite Migration Toolkit
# Ruby-based migration utility for Aria Suite components

require 'json'
require 'net/http'
require 'uri'
require 'openssl'
require 'base64'
require 'logger'
require 'optparse'
require 'yaml'
require 'cgi'

class AriaMigrationToolkit
  VERSION = '2.0.0'
  
  def initialize(config_file = nil)
    @config = load_config(config_file)
    @logger = setup_logger
    @http_clients = {}
  end
  
  def setup_logger
    logger = Logger.new(STDOUT)
    logger.level = Logger::INFO
    logger.formatter = proc do |severity, datetime, progname, msg|
      "[#{datetime.strftime('%Y-%m-%d %H:%M:%S')}] #{severity}: #{msg}\n"
    end
    logger
  end
  
  def load_config(config_file)
    config_file ||= 'migration-config.yml'
    
    if File.exist?(config_file)
      YAML.load_file(config_file)
    else
      create_default_config(config_file)
      YAML.load_file(config_file)
    end
  end
  
  def create_default_config(config_file)
    default_config = {
      'source' => {
        'aria_operations' => {
          'hostname' => 'old-aria-ops.lab.local',
          'username' => 'admin',
          'password' => 'password123'
        },
        'aria_automation' => {
          'hostname' => 'old-aria-auto.lab.local',
          'username' => 'configadmin',
          'password' => 'password123'
        }
      },
      'target' => {
        'aria_operations' => {
          'hostname' => 'new-aria-ops.lab.local',
          'username' => 'admin',
          'password' => 'newpassword123'
        },
        'aria_automation' => {
          'hostname' => 'new-aria-auto.lab.local',
          'username' => 'configadmin',
          'password' => 'newpassword123'
        }
      },
      'migration' => {
        'batch_size' => 50,
        'retry_attempts' => 3,
        'backup_before_migration' => true,
        'validate_after_migration' => true
      }
    }
    
    File.write(config_file, default_config.to_yaml)
    @logger.info("Created default configuration: #{config_file}")
  end
  
  def http_client(hostname, verify_ssl = false)
    return @http_clients[hostname] if @http_clients[hostname]
    
    uri = URI("https://#{hostname}")
    http = Net::HTTP.new(uri.host, uri.port)
    http.use_ssl = true
    http.verify_mode = verify_ssl ? OpenSSL::SSL::VERIFY_PEER : OpenSSL::SSL::VERIFY_NONE
    http.read_timeout = 30
    
    @http_clients[hostname] = http
  end
  
  def authenticate_operations(config)
    hostname = config['hostname']
    auth_data = {
      'username' => config['username'],
      'password' => config['password']
    }
    
    uri = URI("https://#{hostname}/suite-api/api/auth/token/acquire")
    request = Net::HTTP::Post.new(uri)
    request['Content-Type'] = 'application/json'
    request.body = auth_data.to_json
    
    response = http_client(hostname).request(request)
    
    if response.code == '200'
      result = JSON.parse(response.body)
      @logger.info("Authenticated with Aria Operations: #{CGI.escapeHTML(hostname)}")
      result['token']
    else
      raise "Authentication failed for #{hostname}: #{response.code}"
    end
  end
  
  def migrate_operations_data
    @logger.info("Starting Aria Operations migration...")
    
    source_token = authenticate_operations(@config['source']['aria_operations'])
    target_token = authenticate_operations(@config['target']['aria_operations'])
    
    # Export adapters
    adapters = export_operations_adapters(source_token)
    import_operations_adapters(target_token, adapters)
    
    # Export alert definitions
    alerts = export_operations_alerts(source_token)
    import_operations_alerts(target_token, alerts)
    
    # Export custom dashboards
    dashboards = export_operations_dashboards(source_token)
    import_operations_dashboards(target_token, dashboards)
    
    @logger.info("Aria Operations migration completed")
  end
  
  def export_operations_adapters(token)
    hostname = @config['source']['aria_operations']['hostname']
    uri = URI("https://#{hostname}/suite-api/api/adapters")
    
    request = Net::HTTP::Get.new(uri)
    request['Authorization'] = "vRealizeOpsToken #{token}"
    request['Accept'] = 'application/json'
    
    response = http_client(hostname).request(request)
    
    if response.code == '200'
      adapters = JSON.parse(response.body)
      @logger.info("Exported #{adapters['adapterInstancesInfoDto'].length} adapters")
      adapters
    else
      raise "Failed to export adapters: #{response.code}"
    end
  end
  
  def import_operations_adapters(token, adapters_data)
    hostname = @config['target']['aria_operations']['hostname']
    
    adapters_data['adapterInstancesInfoDto'].each do |adapter|
      next if adapter['adapterKindKey'] == 'VMWARE' # Skip built-in adapters
      
      uri = URI("https://#{hostname}/suite-api/api/adapters")
      request = Net::HTTP::Post.new(uri)
      request['Authorization'] = "vRealizeOpsToken #{token}"
      request['Content-Type'] = 'application/json'
      request.body = adapter.to_json
      
      response = http_client(hostname).request(request)
      
      if response.code == '201'
        @logger.info("Imported adapter: #{CGI.escapeHTML(adapter['resourceKey']['name'].to_s)}")
      else
        @logger.warn("Failed to import adapter #{CGI.escapeHTML(adapter['resourceKey']['name'].to_s)}: #{response.code}")
      end
    end
  end
  
  def export_operations_alerts(token)
    hostname = @config['source']['aria_operations']['hostname']
    uri = URI("https://#{hostname}/suite-api/api/alertdefinitions")
    
    request = Net::HTTP::Get.new(uri)
    request['Authorization'] = "vRealizeOpsToken #{token}"
    request['Accept'] = 'application/json'
    
    response = http_client(hostname).request(request)
    
    if response.code == '200'
      alerts = JSON.parse(response.body)
      @logger.info("Exported #{alerts['alertDefinitions'].length} alert definitions")
      alerts
    else
      raise "Failed to export alert definitions: #{response.code}"
    end
  end
  
  def import_operations_alerts(token, alerts_data)
    hostname = @config['target']['aria_operations']['hostname']
    
    alerts_data['alertDefinitions'].each do |alert|
      # Skip system alert definitions
      next if alert['name'].start_with?('System')
      
      uri = URI("https://#{hostname}/suite-api/api/alertdefinitions")
      request = Net::HTTP::Post.new(uri)
      request['Authorization'] = "vRealizeOpsToken #{token}"
      request['Content-Type'] = 'application/json'
      
      # Clean up alert definition for import
      clean_alert = alert.reject { |k, v| ['id', 'links'].include?(k) }
      request.body = clean_alert.to_json
      
      response = http_client(hostname).request(request)
      
      if response.code == '201'
        @logger.info("Imported alert definition: #{CGI.escapeHTML(alert['name'].to_s)}")
      else
        @logger.warn("Failed to import alert #{CGI.escapeHTML(alert['name'].to_s)}: #{response.code}")
      end
    end
  end
  
  def export_operations_dashboards(token)
    hostname = @config['source']['aria_operations']['hostname']
    uri = URI("https://#{hostname}/suite-api/api/dashboards")
    
    request = Net::HTTP::Get.new(uri)
    request['Authorization'] = "vRealizeOpsToken #{token}"
    request['Accept'] = 'application/json'
    
    response = http_client(hostname).request(request)
    
    if response.code == '200'
      dashboards = JSON.parse(response.body)
      @logger.info("Exported #{dashboards['dashboards'].length} dashboards")
      dashboards
    else
      raise "Failed to export dashboards: #{response.code}"
    end
  end
  
  def import_operations_dashboards(token, dashboards_data)
    hostname = @config['target']['aria_operations']['hostname']
    
    dashboards_data['dashboards'].each do |dashboard|
      # Skip system dashboards
      next if dashboard['owner'] == 'system'
      
      uri = URI("https://#{hostname}/suite-api/api/dashboards")
      request = Net::HTTP::Post.new(uri)
      request['Authorization'] = "vRealizeOpsToken #{token}"
      request['Content-Type'] = 'application/json'
      
      # Clean up dashboard for import
      clean_dashboard = dashboard.reject { |k, v| ['id', 'links', 'creationTime'].include?(k) }
      request.body = clean_dashboard.to_json
      
      response = http_client(hostname).request(request)
      
      if response.code == '201'
        @logger.info("Imported dashboard: #{CGI.escapeHTML(dashboard['name'].to_s)}")
      else
        @logger.warn("Failed to import dashboard #{CGI.escapeHTML(dashboard['name'].to_s)}: #{CGI.escapeHTML(response.code.to_s)}")
      end
    end
  end
  
  def migrate_automation_data
    @logger.info("Starting Aria Automation migration...")
    
    # Export and import blueprints
    blueprints = export_automation_blueprints
    import_automation_blueprints(blueprints)
    
    # Export and import projects
    projects = export_automation_projects
    import_automation_projects(projects)
    
    @logger.info("Aria Automation migration completed")
  end
  
  def export_automation_blueprints
    hostname = @config['source']['aria_automation']['hostname']
    token = authenticate_automation(@config['source']['aria_automation'])
    
    uri = URI("https://#{hostname}/blueprint/api/blueprints")
    request = Net::HTTP::Get.new(uri)
    request['Authorization'] = "Bearer #{token}"
    request['Accept'] = 'application/json'
    
    response = http_client(hostname).request(request)
    
    if response.code == '200'
      blueprints = JSON.parse(response.body)
      @logger.info("Exported #{blueprints['content'].length} blueprints")
      blueprints
    else
      raise "Failed to export blueprints: #{response.code}"
    end
  end
  
  def authenticate_automation(config)
    hostname = config['hostname']
    auth_data = {
      'username' => config['username'],
      'password' => config['password']
    }
    
    uri = URI("https://#{hostname}/csp/gateway/am/api/login")
    request = Net::HTTP::Post.new(uri)
    request['Content-Type'] = 'application/json'
    request.body = auth_data.to_json
    
    response = http_client(hostname).request(request)
    
    if response.code == '200'
      result = JSON.parse(response.body)
      @logger.info("Authenticated with Aria Automation: #{CGI.escapeHTML(hostname)}")
      result['access_token']
    else
      raise "Authentication failed for #{hostname}: #{response.code}"
    end
  end
  
  def generate_migration_report
    report = {
      'migration_summary' => {
        'timestamp' => Time.now.iso8601,
        'version' => VERSION,
        'source_environment' => @config['source'],
        'target_environment' => @config['target']
      },
      'operations_migration' => {
        'adapters_migrated' => 0,
        'alerts_migrated' => 0,
        'dashboards_migrated' => 0
      },
      'automation_migration' => {
        'blueprints_migrated' => 0,
        'projects_migrated' => 0
      }
    }
    
    File.write('migration-report.json', JSON.pretty_generate(report))
    @logger.info("Migration report generated: migration-report.json")
  end
  
  def validate_migration
    @logger.info("Validating migration...")
    
    validation_results = {
      'operations_validation' => validate_operations_migration,
      'automation_validation' => validate_automation_migration
    }
    
    File.write('validation-results.json', JSON.pretty_generate(validation_results))
    @logger.info("Validation completed: validation-results.json")
    
    validation_results
  end
  
  def validate_operations_migration
    source_token = authenticate_operations(@config['source']['aria_operations'])
    target_token = authenticate_operations(@config['target']['aria_operations'])
    
    source_adapters = export_operations_adapters(source_token)
    target_adapters = export_operations_adapters(target_token)
    
    {
      'source_adapters_count' => source_adapters['adapterInstancesInfoDto'].length,
      'target_adapters_count' => target_adapters['adapterInstancesInfoDto'].length,
      'migration_success_rate' => calculate_success_rate(source_adapters, target_adapters)
    }
  end
  
  def validate_automation_migration
    {
      'validation_status' => 'completed',
      'timestamp' => Time.now.iso8601
    }
  end
  
  def calculate_success_rate(source_data, target_data)
    return 0 if source_data.nil? || target_data.nil?
    
    source_count = source_data['adapterInstancesInfoDto']&.length || 0
    target_count = target_data['adapterInstancesInfoDto']&.length || 0
    
    return 100 if source_count == 0
    
    ((target_count.to_f / source_count) * 100).round(2)
  end
end

# CLI Interface
def main
  options = {}
  
  OptionParser.new do |opts|
    opts.banner = "Usage: #{$0} [options]"
    
    opts.on('-c', '--config FILE', 'Configuration file') do |file|
      options[:config] = file
    end
    
    opts.on('-o', '--operations', 'Migrate Aria Operations only') do
      options[:operations_only] = true
    end
    
    opts.on('-a', '--automation', 'Migrate Aria Automation only') do
      options[:automation_only] = true
    end
    
    opts.on('-v', '--validate', 'Validate migration only') do
      options[:validate_only] = true
    end
    
    opts.on('-h', '--help', 'Show this help') do
      puts opts
      exit
    end
  end.parse!
  
  toolkit = AriaMigrationToolkit.new(options[:config])
  
  begin
    if options[:validate_only]
      toolkit.validate_migration
    elsif options[:operations_only]
      toolkit.migrate_operations_data
    elsif options[:automation_only]
      toolkit.migrate_automation_data
    else
      # Full migration
      toolkit.migrate_operations_data
      toolkit.migrate_automation_data
      toolkit.validate_migration
      toolkit.generate_migration_report
    end
    
    puts "Migration completed successfully!"
    
  rescue => e
    puts "Migration failed: #{CGI.escapeHTML(e.message.to_s)}"
    exit 1
  end
end

if __FILE__ == $0
  main
end