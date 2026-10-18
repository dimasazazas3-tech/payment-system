const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Платіжна система з комісією", function () {
  let owner, alice, bob, collector, processor;
  const FEE_BPS = 250n; // 2.5 %

  beforeEach(async () => {
    [owner, alice, bob] = await ethers.getSigners();
    collector = await (await ethers.getContractFactory("FeeCollector")).deploy();
    processor = await (await ethers.getContractFactory("PaymentProcessor")).deploy(
      await collector.getAddress(),
      FEE_BPS
    );
    await collector.setProcessor(await processor.getAddress());
  });

  it("надсилає отримувачу суму мінус комісія, а комісію — у FeeCollector", async () => {
    const amount = ethers.parseEther("1");
    const fee = (amount * FEE_BPS) / 10000n;
    await expect(processor.connect(alice).pay(bob.address, { value: amount }))
      .to.changeEtherBalances(
        [alice, bob, collector],
        [-amount, amount - fee, fee]
      );
    expect(await collector.totalCollected()).to.equal(fee);
    expect(await processor.totalVolume()).to.equal(amount);
  });

  it("емітує подію та зберігає історію", async () => {
    const amount = ethers.parseEther("2");
    const fee = (amount * FEE_BPS) / 10000n;
    await expect(processor.connect(alice).pay(bob.address, { value: amount }))
      .to.emit(processor, "PaymentProcessed")
      .withArgs(0, alice.address, bob.address, amount, fee);
    expect(await processor.paymentsCount()).to.equal(1);
    const aliceHist = await processor.getUserPayments(alice.address);
    const bobHist = await processor.getUserPayments(bob.address);
    expect(aliceHist.length).to.equal(1);
    expect(bobHist[0].amount).to.equal(amount);
  });

  it("відхиляє нульову суму та нульову адресу", async () => {
    await expect(processor.pay(bob.address, { value: 0 })).to.be.revertedWithCustomError(processor, "ZeroAmount");
    await expect(processor.pay(ethers.ZeroAddress, { value: 1 })).to.be.revertedWithCustomError(processor, "ZeroAddress");
  });

  it("власник змінює комісію, ліміт 10 %", async () => {
    await processor.setFeeBps(500);
    expect(await processor.feeBps()).to.equal(500);
    await expect(processor.setFeeBps(1001)).to.be.revertedWithCustomError(processor, "FeeTooHigh");
    await expect(processor.connect(alice).setFeeBps(1)).to.be.revertedWithCustomError(processor, "NotOwner");
  });

  it("з нульовою комісією весь платіж іде отримувачу", async () => {
    await processor.setFeeBps(0);
    const amount = ethers.parseEther("1");
    await expect(processor.connect(alice).pay(bob.address, { value: amount }))
      .to.changeEtherBalances([alice, bob, collector], [-amount, amount, 0]);
  });

  it("FeeCollector приймає комісію лише від PaymentProcessor", async () => {
    await expect(collector.connect(alice).collectFee(alice.address, { value: 1 }))
      .to.be.revertedWithCustomError(collector, "NotProcessor");
  });

  it("власник виводить прибуток; сторонні — ні", async () => {
    const amount = ethers.parseEther("10");
    const fee = (amount * FEE_BPS) / 10000n;
    await processor.connect(alice).pay(bob.address, { value: amount });

    await expect(collector.connect(alice).withdrawAll()).to.be.revertedWithCustomError(collector, "NotOwner");
    await expect(collector.withdraw(owner.address, fee + 1n)).to.be.revertedWithCustomError(collector, "InsufficientBalance");

    await expect(collector.withdraw(owner.address, fee / 2n))
      .to.changeEtherBalances([collector, owner], [-(fee / 2n), fee / 2n]);
    await expect(collector.withdrawAll()).to.changeEtherBalance(collector, -(fee - fee / 2n));
    expect(await collector.totalWithdrawn()).to.equal(fee);
  });
});
