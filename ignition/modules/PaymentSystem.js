const { buildModule } = require("@nomicfoundation/hardhat-ignition/modules");

module.exports = buildModule("PaymentSystemModule", (m) => {
  // Початкова комісія: 250 б.п. = 2.5 %
  const feeBps = m.getParameter("feeBps", 250);

  // 1) FeeCollector (власник = акаунт, що деплоїть)
  const feeCollector = m.contract("FeeCollector");

  // 2) PaymentProcessor знає адресу FeeCollector
  const paymentProcessor = m.contract("PaymentProcessor", [feeCollector, feeBps]);

  // 3) FeeCollector дозволяє комісії лише від PaymentProcessor
  m.call(feeCollector, "setProcessor", [paymentProcessor]);

  return { feeCollector, paymentProcessor };
});
