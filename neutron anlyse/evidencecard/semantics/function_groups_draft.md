# 证据功能归类草稿
本文件由已有人工 `applicability` 标签机械归并生成；它不是最终语义单元。下一步须逐组审阅成员证据，确认、拆分或合并其实际支撑含义。
## F01_observed_data_qualification：观测异常与数据合格性核查
- 成员数：104
- 来源标签：data_qualification, missing_data_check, spike_data_qualification, stuck_signal_screening
- 暂定功能总结：针对缺失、零/近零、尖峰、离群、卡滞或不合理读数的识别、保留、剔除或进一步核查依据。
- 代表证据：
  - `IAEA-NP-T-1.1-4-01`：The IAEA guidance states that monitored-instrument condition is assessed from data recorded over a defined period under specific plant conditions, with like and reference sensor outputs available as relevant inputs.
  - `IAEA-NP-T-1.1-4.2.4-01`：For reliable physical-model monitoring, the guidance requires current configuration and operational-state information, including relevant outage or maintenance modifications. It distinguishes this requirement from empirical calibration monitoring.
  - `IAEA-NP-T-1.1-5.1.1-01`：The document lists common data-quality issues in historical monitoring data, including missing points, single or multiple outliers, stuck values, random or unreasonable values, loss of significant digits and dead band. It recommends identifying such issues before model-based analysis.

## F02_reference_and_temporal_pattern：基线、参考与时间模式比较
- 成员数：96
- 来源标签：baseline_reference_selection, neutron_current_temporal_comparison
- 暂定功能总结：针对参考窗口、基线、历史时间模式或变化过程比较的依据。
- 代表证据：
  - `IAEA-NP-T-1.1-4-01`：The IAEA guidance states that monitored-instrument condition is assessed from data recorded over a defined period under specific plant conditions, with like and reference sensor outputs available as relevant inputs.
  - `IAEA-NP-T-1.1-4.2.1-01`：The guidance separates steady-state measurements for instrument dynamic performance and redundant-sensor consistency checks. It states that static consistency must be evaluated at equilibrium because redundant sensors may agree at steady state but diverge during a transient.
  - `IAEA-NP-T-1.1-5.1.1-02`：The guidance requires training data to cover expected operating conditions and warns that historian compression and interpolation can reduce data fidelity and severely alter sensor correlations.

## F03_acquisition_recording_integrity：采样、时间戳与记录完整性
- 成员数：46
- 来源标签：historian_sampling_check
- 暂定功能总结：针对采样频率、时间戳、压缩、导出、记录完整性或同步记录质量的依据。
- 代表证据：
  - `IAEA-NP-T-1.1-4.1.1-01`：Manual collection can compare redundant sensors at a steady temperature plateau, but non-simultaneous measurements make intercomparison and empirical modelling difficult and can introduce recording errors.
  - `IAEA-NP-T-1.1-4.1.2-01`：A plant computer historian simultaneously samples data from a variety of instruments and stores timestamps. The document notes that historian compression and limited sampling frequency or dynamic range can affect the suitability of data for some analyses.
  - `IAEA-NP-T-1.1-4.1.2-02`：The historian description states that simultaneous timestamped samples may be compressed by change thresholds. It notes that limited sampling frequency and dynamic range normally prevent plant-computer data from supporting high-frequency dynamic analysis.

## F04_signal_path_and_conditioning：信号链路、隔离与调理
- 成员数：87
- 来源标签：neutron_current_signal_path_context, signal_path_context
- 暂定功能总结：针对传感器至记录端之间的信号传输、隔离、调理、滤波、增益或链路配置的依据。
- 代表证据：
  - `EPRI-TR-104965-2.3.4-01`：The document states that on-line monitoring signals are commonly acquired from isolated outputs of monitored instrument loops, and defines a channel as including the sensor, isolator and intervening components.
  - `IAEA-NP-T-1.1-4.1.3-01`：Dedicated acquisition can be configured for the required format, sampling frequency, and timing with higher accuracy than a typical plant computer, but requires safe isolation and practical hardware access.
  - `IAEA-NP-T-1.1-4.1.5-01`：The guidance identifies self-powered flux-detector current as an analogue sensor output and specifies current-to-voltage conversion before isolation. It distinguishes signal isolation from filtering or amplification.

## F05_cross_channel_consistency：通道与可比测量一致性
- 成员数：57
- 来源标签：channel_comparison, neutron_current_channel_comparison
- 暂定功能总结：针对与其他通道、冗余/相关传感器或其他工厂指示进行一致性比较的依据。
- 代表证据：
  - `EPRI-TR-104965-2.3.3-01`：The document explains that monitored channels can be compared with a parameter estimate, including estimates formed from redundant channels. A channel's deviation is evaluated against a specified acceptance criterion whose interpretation depends on the estimation method and uncertainty.
  - `IAEA-NP-T-1.1-4.1.1-01`：Manual collection can compare redundant sensors at a steady temperature plateau, but non-simultaneous measurements make intercomparison and empirical modelling difficult and can introduce recording errors.
  - `IAEA-NP-T-1.1-4.2.1-01`：The guidance separates steady-state measurements for instrument dynamic performance and redundant-sensor consistency checks. It states that static consistency must be evaluated at equilibrium because redundant sensors may agree at steady state but diverge during a transient.

## F06_test_and_calibration_alignment：测试、通道检查与校准活动
- 成员数：34
- 来源标签：calibration_activity_check
- 暂定功能总结：针对测试、通道检查、校准活动及其时间对齐或数据排除条件的依据。
- 代表证据：
  - `IAEA-NP-T-1.1-4.2.2-01`：The guidance lists operational changes such as trips, startup power steps, pump changes, and power stepback as opportunities to record instrumentation dynamic response and derive response-time or promptness parameters.
  - `IAEA-TECDOC-1830-2.2.1.3-01`：The document identifies spikes and outliers as potential data problems. It notes that spikes can be associated with channel checks or calibration activity, may be difficult to remove automatically, and data acquired during calibration should be excluded from calibration-monitoring analysis.
  - `IAEA-TECDOC-1830-2.2.1.3-02`：The document states that calibration or channel-check spikes can remain within calibrated range and may require manual removal; data recorded during channel calibration should be excluded from calibration-monitoring analysis.

## F07_neutron_measurement_context：中子测量原理与仪表构型
- 成员数：50
- 来源标签：neutron_current_measurement_context
- 暂定功能总结：针对中子电流测量原理、探测器/通道构型、量程或仪表解释边界的依据。
- 代表证据：
  - `IAEA-DIGITAL-IC-MODERNIZATION-03`：When existing sensors are connected to a new I&C system, interface accuracy requirements and time constants need definition and the equipment must be qualified for expected conditions. For safety-system inputs, the guidance calls for sufficient dynamic range and explicitly defined responses when one or more sensors are invalid; it does not provide generic numeric limits for a neutron-current channel.
  - `IAEA-SSG-70-04`：The guide explicitly lists neutron flux and distribution, rate of flux change, axial power distribution and power oscillation among parameters for which safety-system settings can be required. Applicable settings vary by plant mode, design and reactor type.
  - `NRC-IC-EMERGING-TECH-01`：Moving from periodic inspection toward online monitoring requires more than an algorithm: the report identifies sensors, understanding of what and how to measure, data interrogation, communication and integration, predictive models, deployment integration and maintenance philosophy. Surveillance applications include response-time measurement and predictive analysis of sensors and sensor lines.

## F08_detector_response_and_calibration：探测器响应与标定特性
- 成员数：34
- 来源标签：detector_calibration_context, detector_response_time_context
- 暂定功能总结：针对探测器动态响应、响应时间、灵敏度、标定曲线或响应漂移的依据。
- 代表证据：
  - `IAEA-NP-T-1.1-4.2.2-01`：The guidance lists operational changes such as trips, startup power steps, pump changes, and power stepback as opportunities to record instrumentation dynamic response and derive response-time or promptness parameters.
  - `IAEA-DIGITAL-IC-MODERNIZATION-02`：Digital I&C signals are sampled, digitized, transmitted and processed sequentially; existing functional specifications therefore need detailed reconsideration when moved to a digital design. Processing load and timing sequences can affect transmission and response time, so observed temporal patterns must be interpreted with acquisition-path context rather than as process behaviour by default.
  - `IAEA-DIGITAL-IC-MODERNIZATION-03`：When existing sensors are connected to a new I&C system, interface accuracy requirements and time constants need definition and the equipment must be qualified for expected conditions. For safety-system inputs, the guidance calls for sufficient dynamic range and explicitly defined responses when one or more sensors are invalid; it does not provide generic numeric limits for a neutron-current channel.

## F09_gamma_and_mixed_field_context：伽马与混合辐射场影响
- 成员数：14
- 来源标签：gamma_contribution_check
- 暂定功能总结：针对伽马贡献、混合辐射场、干扰或补偿边界的依据。
- 代表证据：
  - `ANIMMA-NUCLEAR-INSTRUMENTATION-2.1-01`：The review distinguishes pulse, Campbell, and current operating modes for fission chambers. In current mode, collected charge is integrated to an average current proportional to fission rate and neutron flux, while gamma contribution can be significant at high flux.
  - `ANIMMA-NUCLEAR-INSTRUMENTATION-2.1-02`：The Campbell mode uses the variance or mean square of detector current and is intended for an intermediate flux regime; its weighting suppresses gamma-induced contribution relative to neutron-induced contribution.
  - `ANIMMA-NUCLEAR-INSTRUMENTATION-2.2-02`：Prompt self-powered neutron detectors can have quasi-instantaneous response, but the review notes lower neutron efficiency and a higher relative contribution from external gamma rays than for delayed detectors.

## F10_generic_signal_quality：通用信号质量与监测边界
- 成员数：98
- 来源标签：signal_quality_context
- 暂定功能总结：针对噪声、漂移、监测质量、模型适用范围或一般信号可信度的依据。
- 代表证据：
  - `IAEA-TECDOC-1830-2.2.2-01`：Before dynamic OLM analysis, raw data should be screened for suitability. The document lists amplitude distribution, variance, skewness, and kurtosis and notes checking stationarity and linearity before rigorous dynamic analysis.
  - `IAEA-DIGITAL-IC-MODERNIZATION-01`：Digital I&C modernization requires verification and validation across design phases because system functions and subsystem interactions must preserve plant safety. Software introduces deterministic common-cause failure modes, so redundant channels alone do not provide the assurance expected from an analogue arrangement.
  - `IAEA-DIGITAL-IC-MODERNIZATION-06`：After handover, the utility remains responsible for configuration control and change management. Loss of configuration control can degrade quality and may render an installed system functionally inoperative, so data review should retain the relevant acquisition configuration and modification context.
