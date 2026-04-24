from dataclasses import dataclass
from typing import Optional, TypeVar
from datetime import datetime
import re
import tiktoken
from openai import OpenAI
from loguru import logger
import json
RawPaperItem = TypeVar('RawPaperItem')


def _is_chinese_language(lang: str | None) -> bool:
    normalized = str(lang or '').lower()
    return 'chinese' in normalized or '中文' in normalized


def _contains_chinese(text: str | None) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', text or ''))


@dataclass
class Paper:
    source: str
    title: str
    authors: list[str]
    abstract: str
    url: str
    pdf_url: Optional[str] = None
    full_text: Optional[str] = None
    tldr: Optional[str] = None
    affiliations: Optional[list[str]] = None
    score: Optional[float] = None

    def _translate_text(self, openai_client: OpenAI, llm_params: dict, text: str, lang: str) -> str:
        response = openai_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": f"You are a scientific translator. Translate the input into {lang}. Return only the translated text with no explanation.",
                },
                {
                    "role": "user",
                    "content": text,
                },
            ],
            **llm_params.get('generation_kwargs', {})
        )
        return (response.choices[0].message.content or '').strip()

    def _generate_tldr_with_llm(self, openai_client:OpenAI,llm_params:dict) -> str:
        lang = llm_params.get('language', 'English')
        if _is_chinese_language(lang):
            prompt = (
                "Please write a one-sentence TLDR of the following paper in Simplified Chinese. "
                "The final answer must be Chinese only and should not contain any English sentence.\n\n"
            )
        else:
            prompt = f"Given the following information of a paper, generate a one-sentence TLDR summary in {lang}:\n\n"
        if self.title:
            prompt += f"Title:\n {self.title}\n\n"

        if self.abstract:
            prompt += f"Abstract: {self.abstract}\n\n"

        if self.full_text:
            prompt += f"Preview of main content:\n {self.full_text}\n\n"

        if not self.full_text and not self.abstract:
            logger.warning(f"Neither full text nor abstract is provided for {self.url}")
            if _is_chinese_language(lang):
                return "无法生成摘要：缺少论文正文和摘要信息。"
            return "Failed to generate TLDR. Neither full text nor abstract is provided"
        
        enc = tiktoken.encoding_for_model("gpt-4o")
        prompt_tokens = enc.encode(prompt)
        prompt_tokens = prompt_tokens[:4000]
        prompt = enc.decode(prompt_tokens)
        
        system_prompt = (
            f"You are an assistant who summarizes scientific papers accurately. "
            f"Your answer must be written in {lang}."
        )
        if _is_chinese_language(lang):
            system_prompt += " Always return Simplified Chinese only. Do not answer in English."

        response = openai_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {"role": "user", "content": prompt},
            ],
            **llm_params.get('generation_kwargs', {})
        )
        tldr = (response.choices[0].message.content or '').strip()
        if _is_chinese_language(lang) and not _contains_chinese(tldr):
            logger.warning(f"TLDR for {self.url} was not returned in Chinese. Translating it.")
            translated = self._translate_text(openai_client, llm_params, tldr, lang)
            if translated:
                tldr = translated
        return tldr
    
    def generate_tldr(self, openai_client:OpenAI,llm_params:dict) -> str:
        lang = llm_params.get('language', 'English')
        try:
            tldr = self._generate_tldr_with_llm(openai_client,llm_params)
            self.tldr = tldr
            return tldr
        except Exception as e:
            logger.warning(f"Failed to generate tldr of {self.url}: {e}")
            tldr = self.abstract
            if _is_chinese_language(lang) and tldr and not _contains_chinese(tldr):
                try:
                    tldr = self._translate_text(openai_client, llm_params, tldr, lang)
                except Exception as translate_error:
                    logger.warning(f"Failed to translate fallback TLDR of {self.url}: {translate_error}")
            self.tldr = tldr
            return tldr

    def _generate_affiliations_with_llm(self, openai_client:OpenAI,llm_params:dict) -> Optional[list[str]]:
        if self.full_text is not None:
            prompt = f"Given the beginning of a paper, extract the affiliations of the authors in a python list format, which is sorted by the author order. If there is no affiliation found, return an empty list '[]':\n\n{self.full_text}"
            enc = tiktoken.encoding_for_model("gpt-4o")
            prompt_tokens = enc.encode(prompt)
            prompt_tokens = prompt_tokens[:2000]
            prompt = enc.decode(prompt_tokens)
            affiliations = openai_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an assistant who perfectly extracts affiliations of authors from a paper. You should return a python list of affiliations sorted by the author order, like [\"TsingHua University\",\"Peking University\"]. If an affiliation is consisted of multi-level affiliations, like 'Department of Computer Science, TsingHua University', you should return the top-level affiliation 'TsingHua University' only. Do not contain duplicated affiliations. If there is no affiliation found, you should return an empty list [ ]. You should only return the final list of affiliations, and do not return any intermediate results.",
                    },
                    {"role": "user", "content": prompt},
                ],
                **llm_params.get('generation_kwargs', {})
            )
            affiliations = affiliations.choices[0].message.content

            affiliations = re.search(r'\[.*?\]', affiliations, flags=re.DOTALL).group(0)
            affiliations = json.loads(affiliations)
            affiliations = list(set(affiliations))
            affiliations = [str(a) for a in affiliations]

            return affiliations
    
    def generate_affiliations(self, openai_client:OpenAI,llm_params:dict) -> Optional[list[str]]:
        try:
            affiliations = self._generate_affiliations_with_llm(openai_client,llm_params)
            self.affiliations = affiliations
            return affiliations
        except Exception as e:
            logger.warning(f"Failed to generate affiliations of {self.url}: {e}")
            self.affiliations = None
            return None
@dataclass
class CorpusPaper:
    title: str
    abstract: str
    added_date: datetime
    paths: list[str]