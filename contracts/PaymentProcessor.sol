// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

interface IFeeCollector {
    function collectFee(address payer) external payable;
}

/**
 * @title PaymentProcessor
 * @notice Приймає платежі, утримує комісію (у базисних пунктах), надсилає комісію
 *         у FeeCollector, а решту Ether — отримувачу.
 */
contract PaymentProcessor {
    uint256 public constant BPS_DENOMINATOR = 10_000;
    uint256 public constant MAX_FEE_BPS = 1_000; // не більше 10 %

    struct Payment {
        address from;
        address to;
        uint256 amount;    // сума, надіслана платником
        uint256 fee;       // комісія
        uint256 timestamp;
    }

    address public owner;
    IFeeCollector public feeCollector;
    uint256 public feeBps;       // 100 = 1 %
    uint256 public totalVolume;  // загальний обіг (брутто)
    Payment[] private payments;
    mapping(address => uint256[]) private userPayments; // індекси платежів учасника

    uint256 private locked = 1; // захист від reentrancy

    event PaymentProcessed(
        uint256 indexed id,
        address indexed from,
        address indexed to,
        uint256 amount,
        uint256 fee
    );
    event FeeChanged(uint256 oldFeeBps, uint256 newFeeBps);

    error NotOwner();
    error ZeroAddress();
    error ZeroAmount();
    error FeeTooHigh();
    error Reentrancy();
    error TransferFailed();
    error IndexOutOfRange();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier nonReentrant() {
        if (locked != 1) revert Reentrancy();
        locked = 2;
        _;
        locked = 1;
    }

    constructor(address _feeCollector, uint256 _feeBps) {
        if (_feeCollector == address(0)) revert ZeroAddress();
        if (_feeBps > MAX_FEE_BPS) revert FeeTooHigh();
        owner = msg.sender;
        feeCollector = IFeeCollector(_feeCollector);
        feeBps = _feeBps;
    }

    /// @notice Розраховує комісію для заданої суми.
    function calculateFee(uint256 amount) public view returns (uint256) {
        return (amount * feeBps) / BPS_DENOMINATOR;
    }

    /// @notice Переказ Ether отримувачу з автоматичною комісією.
    function pay(address payable recipient) external payable nonReentrant {
        if (recipient == address(0)) revert ZeroAddress();
        if (msg.value == 0) revert ZeroAmount();

        uint256 fee = calculateFee(msg.value);
        uint256 net = msg.value - fee;

        uint256 id = payments.length;
        payments.push(Payment(msg.sender, recipient, msg.value, fee, block.timestamp));
        userPayments[msg.sender].push(id);
        if (recipient != msg.sender) userPayments[recipient].push(id);
        totalVolume += msg.value;

        if (fee > 0) {
            feeCollector.collectFee{value: fee}(msg.sender);
        }
        (bool ok, ) = recipient.call{value: net}("");
        if (!ok) revert TransferFailed();

        emit PaymentProcessed(id, msg.sender, recipient, msg.value, fee);
    }

    function setFeeBps(uint256 newFeeBps) external onlyOwner {
        if (newFeeBps > MAX_FEE_BPS) revert FeeTooHigh();
        emit FeeChanged(feeBps, newFeeBps);
        feeBps = newFeeBps;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        owner = newOwner;
    }

    // ----------------------- Перегляд історії -----------------------

    function paymentsCount() external view returns (uint256) {
        return payments.length;
    }

    function getPayment(uint256 id) external view returns (Payment memory) {
        if (id >= payments.length) revert IndexOutOfRange();
        return payments[id];
    }

    /// @notice Усі платежі, у яких адреса є відправником або отримувачем.
    function getUserPayments(address user) external view returns (Payment[] memory result) {
        uint256[] storage ids = userPayments[user];
        result = new Payment[](ids.length);
        for (uint256 i = 0; i < ids.length; i++) {
            result[i] = payments[ids[i]];
        }
    }
}
