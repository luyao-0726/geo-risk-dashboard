/**
 * Vercel Serverless Function — /api/ask
 * 接收用户问题，结合 risk_events_clean.csv 数据调用 DeepSeek API 作答。
 * API Key 通过环境变量 DEEPSEEK_API_KEY 注入，绝不暴露到前端。
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

module.exports = async (req, res) => {
  // ── CORS ──
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: '仅支持 POST 请求' });
  }

  // ── 参数校验 ──
  const { question } = req.body || {};
  if (!question || !question.trim()) {
    return res.status(400).json({ error: '请输入问题' });
  }

  // ── API Key ──
  const apiKey = process.env.DEEPSEEK_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: '服务端未配置 DEEPSEEK_API_KEY 环境变量' });
  }

  // ── 读取 CSV 数据 ──
  let csvData;
  try {
    const csvPath = path.resolve(process.cwd(), 'risk_events_clean.csv');
    csvData = fs.readFileSync(csvPath, 'utf-8');
    // 移除 UTF-8 BOM（﻿），CSV 由 Python utf-8-sig 生成
    if (csvData.charCodeAt(0) === 0xFEFF) {
      csvData = csvData.slice(1);
    }
  } catch (e) {
    return res.status(500).json({ error: '无法读取风险事件数据文件' });
  }

  // ── 调用 DeepSeek ──
  try {
    const answer = await callDeepSeek(apiKey, csvData, question.trim());
    return res.status(200).json({ answer });
  } catch (e) {
    const msg = e.message || 'AI 服务调用失败';
    return res.status(500).json({ error: msg });
  }
};

/**
 * 调用 DeepSeek Chat API
 */
function callDeepSeek(apiKey, csvData, question) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      model: 'deepseek-chat',
      messages: [
        {
          role: 'system',
          content: [
            '你是一位资深企业地缘风险分析师。请严格根据以下 CSV 数据集的内容回答用户的问题。',
            '不要编造或推测数据中不存在的信息。如果数据不足以回答问题，请明确说明。',
            '回答时请引用具体的事件ID（news_id）、日期、国家和风险类型作为依据。',
            '用中文回答，条理清晰，必要时使用分点列举。',
            '',
            'CSV 数据集（企业地缘风险事件库）：',
            csvData
          ].join('\n')
        },
        {
          role: 'user',
          content: question
        }
      ],
      temperature: 0.3,
      max_tokens: 2000
    });

    const options = {
      hostname: 'api.deepseek.com',
      path: '/v1/chat/completions',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      timeout: 25000
    };

    const httpReq = https.request(options, (httpRes) => {
      let data = '';
      httpRes.on('data', (chunk) => { data += chunk; });
      httpRes.on('end', () => {
        try {
          const json = JSON.parse(data);
          if (json.choices && json.choices[0] && json.choices[0].message) {
            resolve(json.choices[0].message.content);
          } else if (json.error) {
            reject(new Error(json.error.message || 'DeepSeek API 返回错误'));
          } else {
            reject(new Error('API 返回格式异常'));
          }
        } catch (_e) {
          reject(new Error('解析 API 响应失败'));
        }
      });
    });

    httpReq.on('error', (e) => {
      reject(new Error(`网络请求失败: ${e.message}`));
    });
    httpReq.on('timeout', () => {
      httpReq.destroy();
      reject(new Error('API 请求超时，请稍后重试'));
    });

    httpReq.write(body);
    httpReq.end();
  });
}
