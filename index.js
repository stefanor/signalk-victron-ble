const { spawn } = require('child_process')

const schema = require('./schema')

const pkgData = require('./package.json')

module.exports = function (app) {
  let child
  function sleep(ms) {
    return new Promise((resolve) => {
      setTimeout(resolve, ms);
    });
  }
  function run_python_plugin(options) {
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

      child.on('close', code => {
        if (code !== 0) {
          console.warn(`Plugin exited ${code}, restarting...`)
        }
        child = undefined
      })

      child.stdin.write(JSON.stringify(options))
      child.stdin.write('\n')
  };
  return {
    start: async (options) => {
      while (true) {
        if (child === undefined) {
          run_python_plugin(options);
        }
        await sleep(1000);
      }
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
