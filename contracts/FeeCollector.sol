// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title FeeCollector
 * @notice Отримує комісії від PaymentProcessor і дозволяє власнику виводити прибуток.
 */
contract FeeCollector {
    address public owner;
    address public processor;      // єдиний контракт, якому дозволено надсилати комісію
    uint256 public totalCollected; // всього зібрано за весь час
    uint256 public totalWithdrawn; // всього виведено власником

    event ProcessorSet(address indexed processor);
    event FeeReceived(address indexed payer, uint256 amount);
    event Withdrawn(address indexed to, uint256 amount);
    event OwnershipTransferred(address indexed oldOwner, address indexed newOwner);

    error NotOwner();
    error NotProcessor();
    error ZeroAddress();
    error InsufficientBalance(uint256 requested, uint256 available);
    error TransferFailed();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /// @notice Прив'язує PaymentProcessor (викликається після його деплою).
    function setProcessor(address _processor) external onlyOwner {
        if (_processor == address(0)) revert ZeroAddress();
        processor = _processor;
        emit ProcessorSet(_processor);
    }

    /// @notice Приймає комісію. Викликати може лише PaymentProcessor.
    function collectFee(address payer) external payable {
        if (msg.sender != processor) revert NotProcessor();
        totalCollected += msg.value;
        emit FeeReceived(payer, msg.value);
    }

    /// @notice Виводить частину прибутку на вказану адресу.
    function withdraw(address payable to, uint256 amount) external onlyOwner {
        if (to == address(0)) revert ZeroAddress();
        uint256 bal = address(this).balance;
        if (amount > bal) revert InsufficientBalance(amount, bal);
        totalWithdrawn += amount;
        (bool ok, ) = to.call{value: amount}("");
        if (!ok) revert TransferFailed();
        emit Withdrawn(to, amount);
    }

    /// @notice Виводить весь баланс власнику.
    function withdrawAll() external onlyOwner {
        uint256 bal = address(this).balance;
        if (bal == 0) revert InsufficientBalance(1, 0);
        totalWithdrawn += bal;
        (bool ok, ) = payable(owner).call{value: bal}("");
        if (!ok) revert TransferFailed();
        emit Withdrawn(owner, bal);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    /// @notice Поточний баланс (ще не виведений прибуток).
    function balance() external view returns (uint256) {
        return address(this).balance;
    }
}
