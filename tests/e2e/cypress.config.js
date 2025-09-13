const { defineConfig } = require('cypress')

module.exports = defineConfig({
  e2e: {
    baseUrl: 'https://aria-ops.lab.local',
    supportFile: 'cypress/support/e2e.js',
    specPattern: 'cypress/e2e/**/*.cy.{js,jsx,ts,tsx}',
    videosFolder: 'cypress/videos',
    screenshotsFolder: 'cypress/screenshots',
    fixturesFolder: 'cypress/fixtures',
    
    // Viewport settings
    viewportWidth: 1280,
    viewportHeight: 720,
    
    // Timeouts
    defaultCommandTimeout: 10000,
    requestTimeout: 10000,
    responseTimeout: 10000,
    pageLoadTimeout: 30000,
    
    // Retry settings
    retries: {
      runMode: 2,
      openMode: 0
    },
    
    // Video and screenshot settings
    video: true,
    videoCompression: 32,
    screenshotOnRunFailure: true,
    
    // Environment variables
    env: {
      aria_ops_username: 'admin',
      aria_ops_password: 'VMware123!',
      aria_auto_username: 'configadmin',
      aria_auto_password: 'VMware123!',
      test_timeout: 30000
    },
    
    setupNodeEvents(on, config) {
      // Task definitions
      on('task', {
        log(message) {
          console.log(message)
          return null
        },
        
        // Custom task for API calls
        makeApiCall({ method, url, headers, body }) {
          const https = require('https')
          const { URL } = require('url')
          
          return new Promise((resolve, reject) => {
            const parsedUrl = new URL(url)
            const options = {
              hostname: parsedUrl.hostname,
              port: parsedUrl.port || 443,
              path: parsedUrl.pathname + parsedUrl.search,
              method: method,
              headers: headers || {},
              rejectUnauthorized: false // For self-signed certificates
            }
            
            const req = https.request(options, (res) => {
              let data = ''
              res.on('data', (chunk) => {
                data += chunk
              })
              res.on('end', () => {
                resolve({
                  statusCode: res.statusCode,
                  headers: res.headers,
                  body: data
                })
              })
            })
            
            req.on('error', (error) => {
              reject(error)
            })
            
            if (body) {
              req.write(JSON.stringify(body))
            }
            
            req.end()
          })
        },
        
        // Database operations
        queryDatabase(query) {
          const { Client } = require('pg')
          const client = new Client({
            host: 'localhost',
            port: 5432,
            database: 'aria_dev',
            user: 'aria_user',
            password: 'aria_password'
          })
          
          return client.connect()
            .then(() => client.query(query))
            .then(result => {
              client.end()
              return result.rows
            })
            .catch(error => {
              client.end()
              throw error
            })
        },
        
        // File operations
        readFile(filename) {
          const fs = require('fs')
          return fs.readFileSync(filename, 'utf8')
        },
        
        writeFile({ filename, content }) {
          const fs = require('fs')
          fs.writeFileSync(filename, content)
          return null
        }
      })
      
      // Browser launch options
      on('before:browser:launch', (browser = {}, launchOptions) => {
        if (browser.name === 'chrome') {
          launchOptions.args.push('--disable-web-security')
          launchOptions.args.push('--disable-features=VizDisplayCompositor')
          launchOptions.args.push('--ignore-certificate-errors')
          launchOptions.args.push('--ignore-ssl-errors')
        }
        
        return launchOptions
      })
      
      // Custom commands for reporting
      on('after:spec', (spec, results) => {
        if (results && results.video) {
          // Custom video processing if needed
          console.log('Video recorded:', results.video)
        }
      })
      
      return config
    }
  },
  
  component: {
    devServer: {
      framework: 'react',
      bundler: 'webpack'
    },
    specPattern: 'src/**/*.cy.{js,jsx,ts,tsx}'
  }
})