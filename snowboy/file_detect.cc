#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "snowboy-detect.h"

// 由 CMake 设置为项目自带资源的绝对路径，运行时不依赖当前目录。
#ifndef SNOWBOY_RESOURCE_DIR
#error "Please build this example with CMake."
#endif

int main(int argc, char** argv) {
    if (argc > 4) {
        std::cerr << "Usage: file_detect [audio.raw [model.pmdl|model.umdl [sensitivity]]]\n";
        return 1;
    }

    try {
        const std::string resource_dir = SNOWBOY_RESOURCE_DIR;
        const std::string audio_path = argc > 1 ? argv[1] : resource_dir + "/snowboy.raw";
        const std::string model_path = argc > 2 ? argv[2] : resource_dir + "/models/snowboy.umdl";
        const std::string sensitivity = argc > 3 ? argv[3] : "0.5";
        std::size_t parsed = 0;
        const float value = std::stof(sensitivity, &parsed);
        if (parsed != sensitivity.size() || !std::isfinite(value) || value <= 0 || value >= 1) {
            throw std::runtime_error("Sensitivity must be a number between 0 and 1 (exclusive).");
        }

        std::ifstream audio(audio_path, std::ios::binary);
        if (!audio) {
            throw std::runtime_error("Cannot open audio: " + audio_path);
        }
        // 本例读取裸 PCM，不解析 WAV 文件头。
        char magic[4] = {};
        audio.read(magic, sizeof(magic));
        if (audio.gcount() == 4 && std::string(magic, 4) == "RIFF") {
            throw std::runtime_error("Convert WAV to raw PCM first; see README.md.");
        }
        audio.clear();
        audio.seekg(0, std::ios::end);
        const std::streamoff audio_bytes = audio.tellg();
        if (audio_bytes <= 0 || audio_bytes % sizeof(int16_t) != 0) {
            throw std::runtime_error("Audio must contain complete, non-empty 16-bit PCM samples.");
        }
        audio.seekg(0, std::ios::beg);
        if (!audio) {
            throw std::runtime_error("Cannot seek audio file.");
        }
        const std::string resource_path = resource_dir + "/common.res";
        if (!std::ifstream(resource_path, std::ios::binary) ||
            !std::ifstream(model_path, std::ios::binary)) {
            throw std::runtime_error("Cannot open common.res or the selected model.");
        }

        // 1. 创建一次检测器；连续输入音频时，它会保留跨帧的检测状态。
        snowboy::SnowboyDetect detector(resource_path, model_path);
        detector.SetSensitivity(sensitivity);
        detector.SetAudioGain(1.0);
        detector.ApplyFrontend(false);
        if (detector.NumHotwords() != 1) {
            throw std::runtime_error("This learning example supports one hotword per model.");
        }
        std::cout << "Audio requirements: " << detector.SampleRate() << " Hz, "
                  << detector.NumChannels() << " channel(s), "
                  << detector.BitsPerSample() << " bits\n";
        if (detector.SampleRate() != 16000 || detector.NumChannels() != 1 ||
            detector.BitsPerSample() != 16) {
            throw std::runtime_error("This example expects a 16 kHz mono 16-bit model.");
        }

        // 2. 每次输入 40 ms：16000 * 0.04 = 640 个样本 = 1280 字节。
        std::vector<int16_t> frame(640);
        int detections = 0;
        std::streamoff processed_bytes = 0;
        while (processed_bytes < audio_bytes) {
            const auto remaining = audio_bytes - processed_bytes;
            const auto frame_bytes = static_cast<std::streamoff>(frame.size() * sizeof(int16_t));
            const auto wanted = remaining < frame_bytes ? remaining : frame_bytes;
            if (!audio.read(reinterpret_cast<char*>(frame.data()), wanted)) {
                throw std::runtime_error("Audio read error.");
            }
            processed_bytes += wanted;
            const int samples = static_cast<int>(wanted / sizeof(int16_t));

            // 3. 数组接口的长度单位是样本数；最后一帧标记为文件结束。
            const int result = detector.RunDetection(
                frame.data(), samples, processed_bytes == audio_bytes);
            if (result > 0) {
                ++detections;
                std::cout << "Wake detected! Hotword index: " << result << '\n';
            } else if (result == -1) {
                throw std::runtime_error("Detection error.");
            }
            // result == 0：无事件；result == -2：静音，继续输入下一帧。
        }
        std::cout << "Total detections: " << detections << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << '\n';
        return 1;
    }
}
