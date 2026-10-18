require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.28",
    settings: { optimizer: { enabled: true, runs: 200 } },
  },
  networks: {
    // Нода, яку запускає команда `npx hardhat node`
    localhost: { url: "http://127.0.0.1:8545" },
  },
};
