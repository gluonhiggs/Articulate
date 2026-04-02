import type { PronunciationWord, SampleAnswerResponse, TopicVocabResponse } from '../../types'

export type FeedItemKind = 'pronunciation' | 'sample_answer' | 'topic_vocab'

interface FeedItemBase {
  id: string
  kind: FeedItemKind
}

export interface PronunciationFeedItem extends FeedItemBase {
  kind: 'pronunciation'
  attemptId: number
  transcript: string | null
  pronunciationScore: number | null
  words: PronunciationWord[] | null
  loading: boolean
  error: string | null
}

export interface SampleAnswerFeedItem extends FeedItemBase {
  kind: 'sample_answer'
  data: SampleAnswerResponse | null
  loading: boolean
  error: string | null
}

export interface TopicVocabFeedItem extends FeedItemBase {
  kind: 'topic_vocab'
  vocabData: TopicVocabResponse | null
  loading: boolean
  error: string | null
}

export type FeedItem = PronunciationFeedItem | SampleAnswerFeedItem | TopicVocabFeedItem
