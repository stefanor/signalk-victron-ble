const { spawn } = require('child_process')

const schema = require('./schema')

const pkgData = require('./package.json')

module.exports = function (app) {
  let child
  return {
    start: options => {
      let args = ['plugin.py']
      child = spawn('ve/bin/python', args, { cwd: __dirname })

      child.stdout.on('data', data => {
        app.debug(data.toString())
        try {
          data.toString().split(/\r?\n/).forEach(line => {
            // console.log(JSON.stringify(line))
            if (line.length > 0) {
              app.handleMessage(undefined, JSON.parse(line))
            }
          })
        } catch (e) {
          console.error(e.message)
        }
      })

      child.stderr.on('data', fromChild => {
        console.error(fromChild.toString())
      })

      child.on('error', err => {
        console.error(err)
      })

      child.stdin.write(JSON.stringify(options))
      child.stdin.write('\n')
    },
    stop: () => {
      if (child) {
        process.kill(child.pid)
        child = undefined
      }
    },
    schema,
    id: pkgData.name,
    name: "Victron Instant Data over BLE"
  }
}
